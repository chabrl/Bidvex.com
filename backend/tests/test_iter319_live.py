"""iter319 LIVE HTTP integration tests.

Validates against the running backend:
- Global onboarding (country/province/state conditional validation)
- Country filter on admin applicants listing
- Inline PDF attachment (?inline=1) Content-Type/Disposition
- Screening edit endpoints (re-screen + summary edit + pin preservation)
- Path-traversal protection still in place

NOTE: Uses the pre-seeded screened applicant `APP_ID` from /tmp/careers_test.env
for screening-edit assertions to avoid spamming Claude credits.
"""
from __future__ import annotations
import io
import json
import os
import time
from pathlib import Path

import pytest
import requests

def _load_frontend_env() -> str:
    env_path = Path(__file__).resolve().parents[2] / "frontend" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_env()).rstrip("/")

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"

# /tmp/careers_test.env — pre-seeded IDs
JOB_ID = "f867ae4d-31ed-43c4-b7fc-f82613d8ff6e"  # requires_cv=true
APP_ID = "4baddff7-8dc4-45a8-ab9f-a32977560ec7"  # Marc ProperCV, screening=Yes


# ── Helpers ────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def admin_token() -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                      timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"no token in login response: {r.json()}"
    return tok


@pytest.fixture(scope="session")
def admin_headers(admin_token) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


def _build_pdf(text: str = "Experienced telemarketer with 5 years outbound calling.") -> bytes:
    """Produce a real PDF using reportlab (installed)."""
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for i, line in enumerate(text.split("\n")):
        c.drawString(72, 800 - i * 18, line)
    c.showPage()
    c.save()
    return buf.getvalue()


def _base_form(country: str = "Canada", province: str = "QC", state: str = "",
               email_suffix: str = "ok") -> dict:
    return {
        "first_name": "TEST",
        "last_name": "iter319",
        "email": f"TEST_iter319_{email_suffix}_{int(time.time()*1000)}@example.com",
        "phone": "+15145551234",
        "country": country,
        "province": province,
        "state": state,
        "preferred_language": "en",
        "custom_responses": json.dumps({"Years of auction experience": "5"}),
    }


# ── Global onboarding validation ───────────────────────────────────────

class TestGlobalOnboardingApply:
    def test_missing_country_returns_422(self):
        form = _base_form(country="", email_suffix="nocountry")
        r = requests.post(f"{BASE_URL}/api/careers/jobs/{JOB_ID}/apply",
                          data=form, timeout=20)
        assert r.status_code == 422, r.text
        body = r.json().get("detail", r.json())
        assert body.get("error") == "missing_country"
        assert "message_en" in body and "message_fr" in body

    def test_canada_missing_province_returns_422(self):
        form = _base_form(country="Canada", province="", email_suffix="caprov")
        r = requests.post(f"{BASE_URL}/api/careers/jobs/{JOB_ID}/apply",
                          data=form, timeout=20)
        assert r.status_code == 422, r.text
        body = r.json().get("detail", r.json())
        assert body.get("error") == "missing_province"

    def test_us_missing_state_returns_422(self):
        form = _base_form(country="United States", province="", state="",
                          email_suffix="usstate")
        r = requests.post(f"{BASE_URL}/api/careers/jobs/{JOB_ID}/apply",
                          data=form, timeout=20)
        assert r.status_code == 422, r.text
        body = r.json().get("detail", r.json())
        assert body.get("error") == "missing_state"

    def test_france_no_secondary_required_succeeds(self, admin_headers):
        """France: both province AND state empty must succeed (with valid CV).
        Persist + verify row via admin GET."""
        form = _base_form(country="France", province="", state="",
                          email_suffix="france")
        pdf = _build_pdf("French candidate cv")
        files = {"cv": ("cv.pdf", pdf, "application/pdf")}
        r = requests.post(f"{BASE_URL}/api/careers/jobs/{JOB_ID}/apply",
                          data=form, files=files, timeout=30)
        assert r.status_code == 200, r.text
        app_id = r.json().get("applicant_id") or r.json().get("id")
        assert app_id

        g = requests.get(
            f"{BASE_URL}/api/admin/careers/applicants/{app_id}",
            headers=admin_headers, timeout=15,
        )
        assert g.status_code == 200, g.text
        rec = g.json()
        assert rec["country"] == "France"
        assert rec.get("province", "") == ""
        assert rec.get("state", "") == ""


# ── Country filter ─────────────────────────────────────────────────────

class TestAdminCountryFilter:
    def test_country_canada_filter(self, admin_headers):
        r = requests.get(
            f"{BASE_URL}/api/admin/careers/applicants",
            params={"country": "Canada"},
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 200, r.text
        rows = r.json()
        if isinstance(rows, dict):
            rows = rows.get("applicants") or rows.get("items") or []
        # All returned applicants must be Canada (allow legacy rows without country to be filtered out)
        for row in rows:
            assert row.get("country") == "Canada", row


# ── Inline PDF preview ─────────────────────────────────────────────────

class TestInlinePdfPreview:
    def test_inline_pdf_content_type_and_disposition(self, admin_headers):
        # Fetch the screened applicant to find its CV filename
        g = requests.get(
            f"{BASE_URL}/api/admin/careers/applicants/{APP_ID}",
            headers=admin_headers, timeout=15,
        )
        assert g.status_code == 200, g.text
        cv_url = (g.json().get("attachments") or {}).get("cv_url")
        if not cv_url:
            pytest.skip("seeded applicant has no cv_url attachment")

        # ?inline=1
        r = requests.get(
            f"{BASE_URL}/api/admin/careers/applicants/{APP_ID}/attachments/{cv_url}",
            params={"inline": 1},
            headers=admin_headers, timeout=20,
        )
        assert r.status_code == 200, r.text
        if cv_url.lower().endswith(".pdf"):
            assert r.headers.get("content-type", "").startswith("application/pdf"), r.headers
        assert "inline" in (r.headers.get("content-disposition") or "").lower()

    def test_default_download_is_attachment(self, admin_headers):
        g = requests.get(
            f"{BASE_URL}/api/admin/careers/applicants/{APP_ID}",
            headers=admin_headers, timeout=15,
        )
        cv_url = (g.json().get("attachments") or {}).get("cv_url")
        if not cv_url:
            pytest.skip("seeded applicant has no cv_url attachment")
        r = requests.get(
            f"{BASE_URL}/api/admin/careers/applicants/{APP_ID}/attachments/{cv_url}",
            headers=admin_headers, timeout=20,
        )
        assert r.status_code == 200, r.text
        cd = (r.headers.get("content-disposition") or "").lower()
        assert "attachment" in cd, cd

    def test_path_traversal_blocked_with_inline(self, admin_headers):
        r = requests.get(
            f"{BASE_URL}/api/admin/careers/applicants/{APP_ID}/attachments/..%2F..%2Fetc%2Fpasswd",
            params={"inline": 1},
            headers=admin_headers, timeout=15,
        )
        assert r.status_code in (400, 403, 404), f"expected blocked, got {r.status_code} {r.text[:200]}"


# ── Screening summary edit / re-screen ─────────────────────────────────

class TestScreeningSummaryEdit:
    def test_patch_summary_empty_returns_422(self, admin_headers):
        r = requests.patch(
            f"{BASE_URL}/api/admin/careers/applicants/{APP_ID}/screening/summary",
            json={"summary": "   ", "pin": True},
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 422, r.text
        body = r.json().get("detail", r.json())
        assert body.get("error") == "empty_summary"

    def test_patch_summary_updates_and_pins(self, admin_headers):
        new_summary = f"TEST iter319 edited at {int(time.time())}"
        r = requests.patch(
            f"{BASE_URL}/api/admin/careers/applicants/{APP_ID}/screening/summary",
            json={"summary": new_summary, "pin": True},
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 200, r.text
        out = r.json()
        assert out.get("summary") == new_summary
        assert out.get("summary_edited") is True
        assert out.get("summary_edited_at")
        assert out.get("summary_edited_by") == ADMIN_EMAIL

        # Verify persisted via GET
        g = requests.get(
            f"{BASE_URL}/api/admin/careers/applicants/{APP_ID}",
            headers=admin_headers, timeout=15,
        )
        assert g.status_code == 200
        scr = g.json().get("screening") or {}
        assert scr.get("summary") == new_summary
        assert scr.get("summary_edited") is True

    def test_rescreen_preserves_pinned_summary(self, admin_headers):
        """Re-screen after admin edit must KEEP pinned summary and store new
        LLM output in screening.llm_summary."""
        # Set a known pinned summary first
        pinned = f"TEST iter319 PINNED {int(time.time())}"
        p = requests.patch(
            f"{BASE_URL}/api/admin/careers/applicants/{APP_ID}/screening/summary",
            json={"summary": pinned, "pin": True},
            headers=admin_headers, timeout=15,
        )
        assert p.status_code == 200, p.text

        # Re-screen (live Claude call — uses 1 credit)
        r = requests.post(
            f"{BASE_URL}/api/admin/careers/applicants/{APP_ID}/screen",
            headers=admin_headers, timeout=60,
        )
        assert r.status_code == 200, r.text
        out = r.json()
        # Pinned summary must survive
        assert out.get("summary") == pinned, f"pinned summary lost: {out.get('summary')!r}"
        assert out.get("summary_edited") is True
        # LLM output must be stored separately
        assert out.get("llm_summary"), f"llm_summary missing from re-screen output: {out}"
        assert out.get("recommendation") in ("Yes", "Maybe", "No"), out


# ── Background-screening on apply (live, costs 1 Claude credit) ────────

class TestApplyTriggersBackgroundScreening:
    def test_apply_canada_with_cv_then_screening_completes(self, admin_headers):
        form = _base_form(country="Canada", province="QC", email_suffix="bgscreen")
        pdf = _build_pdf(
            "John Doe — 6 years outbound call-center, fluent EN/FR,"
            " 90% conversion on cold leads, available immediately.\n"
            "Looking for telemarketing role.")
        files = {"cv": ("cv.pdf", pdf, "application/pdf")}
        r = requests.post(f"{BASE_URL}/api/careers/jobs/{JOB_ID}/apply",
                          data=form, files=files, timeout=30)
        assert r.status_code == 200, r.text
        app_id = r.json().get("applicant_id") or r.json().get("id")
        assert app_id

        # Poll for screening completion (up to 35s)
        deadline = time.time() + 35
        status = None
        rec = None
        while time.time() < deadline:
            g = requests.get(
                f"{BASE_URL}/api/admin/careers/applicants/{app_id}",
                headers=admin_headers, timeout=15,
            )
            if g.status_code == 200:
                scr = (g.json() or {}).get("screening") or {}
                status = scr.get("status")
                rec = scr.get("recommendation")
                if status in ("ok", "failed"):
                    break
            time.sleep(2)

        assert status == "ok", f"screening did not complete OK (got status={status})"
        assert rec in ("Yes", "Maybe", "No")
        # Re-fetch full screening to assert summary + model
        g = requests.get(
            f"{BASE_URL}/api/admin/careers/applicants/{app_id}",
            headers=admin_headers, timeout=15,
        )
        scr = (g.json() or {}).get("screening") or {}
        assert isinstance(scr.get("summary"), str) and scr["summary"]
        assert scr.get("model") == "anthropic/claude-sonnet-4-6", scr.get("model")
