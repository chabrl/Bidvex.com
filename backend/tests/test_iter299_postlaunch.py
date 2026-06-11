"""
test_iter299_postlaunch.py — iter299 post-launch hotfix regression suite
========================================================================

Covers:
  P0 — Bill 96 French-title enforcement (qc_bilingual_validator)
  P1 — Last-Chance nudge service wiring (scheduler registration)
  P1 — Outlook-safe email templates (tables only — zero div/flex/grid)
  P1 — Marketplace moderation API (/api/admin/moderation/*)
  P2 — Advanced analytics API (/api/admin/analytics/advanced + /overview)
"""
import glob
import os
import re

import pytest
import requests
from fastapi import HTTPException

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.environ.get("BIDVEX_TEST_BASE", "http://localhost:8001")


@pytest.fixture(scope="module")
def admin_token(test_admin_email, test_admin_password):
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": test_admin_email, "password": test_admin_password},
                      timeout=30)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    return r.json().get("access_token") or r.json().get("token")


# ────────────────────────────────────────────────────────────────────
# P1 — Outlook-safe email templates: tables only, no div/flex/grid
# ────────────────────────────────────────────────────────────────────
FORBIDDEN = [
    (re.compile(r"<div", re.I), "<div"),
    (re.compile(r"display\s*:\s*flex", re.I), "display:flex"),
    (re.compile(r"display\s*:\s*grid", re.I), "display:grid"),
    (re.compile(r"linear-gradient", re.I), "linear-gradient"),
]


def test_email_templates_are_table_only():
    """Every canonical email module must be free of div/flex/grid layout."""
    offenders = []
    for path in glob.glob(os.path.join(BACKEND_DIR, "services", "emails", "*.py")):
        src = open(path, encoding="utf-8").read()
        for rx, label in FORBIDDEN:
            for m in rx.finditer(src):
                line = src[:m.start()].count("\n") + 1
                offenders.append(f"{os.path.basename(path)}:{line} uses {label}")
    assert not offenders, "Outlook-unsafe markup found:\n" + "\n".join(offenders)


def test_storage_panel_renders_tables():
    from services.emails._email_core import _storage_panel
    html = _storage_panel("Title EN", "Titre FR", "Body EN", "Corps FR",
                          cta_url="https://bidvex.com", cta_en="Go", cta_fr="Aller")
    assert "<table" in html
    assert "<div" not in html.lower()
    assert "linear-gradient" not in html.lower()
    assert "Titre FR" in html and "Corps FR" in html


# ────────────────────────────────────────────────────────────────────
# P0 — Bill 96 French title validator
# ────────────────────────────────────────────────────────────────────
def test_bill96_qc_english_title_without_fr_rejected():
    from services.qc_bilingual_validator import assert_qc_bilingual_titles
    with pytest.raises(HTTPException) as exc:
        assert_qc_bilingual_titles(
            title="Solid wood dining table",
            title_fr=None,
            description=None,
            description_fr=None,
            region="QC", city="Montreal", content_language="en",
        )
    assert exc.value.status_code == 422
    assert exc.value.detail["error"] == "qc_french_title_required"
    assert exc.value.detail["message_fr"]  # bilingual error payload


def test_bill96_qc_with_french_title_passes():
    from services.qc_bilingual_validator import assert_qc_bilingual_titles
    # Must not raise
    assert_qc_bilingual_titles(
        title="Solid wood dining table",
        title_fr="Table à manger en bois massif",
        description=None, description_fr=None,
        region="QC", city="Montreal", content_language="en",
    )


def test_bill96_non_qc_listing_not_required():
    from services.qc_bilingual_validator import assert_qc_bilingual_titles
    assert_qc_bilingual_titles(
        title="Solid wood dining table", title_fr=None,
        description=None, description_fr=None,
        region="ON", city="Toronto", content_language="en",
    )


# ────────────────────────────────────────────────────────────────────
# P1 — Last-Chance nudge wiring
# ────────────────────────────────────────────────────────────────────
def test_last_chance_service_importable():
    from services.last_chance import process_last_chance_nudges  # noqa: F401


def test_last_chance_job_registered_in_server():
    src = open(os.path.join(BACKEND_DIR, "server.py"), encoding="utf-8").read()
    assert "last_chance_nudges" in src, "last-chance scheduler job not registered"


# ────────────────────────────────────────────────────────────────────
# P2 — Advanced analytics API
# ────────────────────────────────────────────────────────────────────
def test_advanced_analytics_endpoint(admin_token):
    """/advanced (legacy + gmv merge) must expose a non-empty gmv block."""
    r = requests.get(f"{BASE}/api/admin/analytics/advanced",
                     headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert isinstance(d.get("gmv"), dict) and "all_time" in d["gmv"]
    assert "platform_revenue" in d
    assert "conversion" in d  # legacy block preserved


def test_analytics_overview_alias(admin_token):
    """/overview is the iter299 deep-dive payload consumed by the Admin UI."""
    r = requests.get(f"{BASE}/api/admin/analytics/overview",
                     headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
    assert r.status_code == 200
    d = r.json()
    assert isinstance(d.get("gmv"), dict) and "all_time" in d["gmv"]
    assert "auctions_by_section" in d
    assert "users_by_role" in d
    assert isinstance(d.get("signups_per_day"), list) and len(d["signups_per_day"]) == 30
    assert isinstance(d.get("revenue_per_day"), list) and len(d["revenue_per_day"]) == 30


def test_advanced_analytics_requires_admin():
    r = requests.get(f"{BASE}/api/admin/analytics/advanced", timeout=30)
    assert r.status_code in (401, 403)


# ────────────────────────────────────────────────────────────────────
# P1 — Marketplace moderation API
# ────────────────────────────────────────────────────────────────────
def test_moderation_count(admin_token):
    r = requests.get(f"{BASE}/api/admin/moderation/count",
                     headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
    assert r.status_code == 200
    assert isinstance(r.json().get("pending_review"), int)


def test_moderation_pending_payload(admin_token):
    r = requests.get(f"{BASE}/api/admin/moderation/pending",
                     headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "listings" in d and "total" in d
    for row in d["listings"]:
        assert row.get("section") in ("marketplace", "lots")
        assert "seller_email" in row  # seller enrichment present


def test_moderation_requires_admin():
    r = requests.get(f"{BASE}/api/admin/moderation/pending", timeout=30)
    assert r.status_code in (401, 403)


def test_moderation_reject_requires_reason(admin_token):
    # Rejecting a non-existent listing with an empty reason → 422 (validation)
    r = requests.post(f"{BASE}/api/admin/moderation/nonexistent-id/reject",
                      json={"reason": ""},
                      headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
    assert r.status_code == 422


def test_moderation_404_for_unknown_listing(admin_token):
    r = requests.post(f"{BASE}/api/admin/moderation/nonexistent-id/approve",
                      headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
    assert r.status_code == 404
