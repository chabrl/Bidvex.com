"""iter318 — Live HTTP integration tests for the BidVex Careers module.

Hits the actual preview env via REACT_APP_BACKEND_URL. Verifies PART 1
(Email Hub sender swap) + PART 2 (Careers public/admin/apply paths).
"""
import io
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
JOB_ID = "f867ae4d-31ed-43c4-b7fc-f82613d8ff6e"  # Independent Vehicle Appraiser (requires_cv=true)
JOB2_ID = "38fbfd12-e72a-426a-9d69-10173a1ab2f0"
APPLICANT_ID_SHORTLISTED = None  # discovered at runtime

PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<</Type/Catalog>>endobj\ntrailer<<>>\n%%EOF"
NOT_PDF_BYTES = b"this is not a pdf at all, just plain text masquerading"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                      timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    return j.get("access_token") or j.get("token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# --- PART 1: Email Hub sender ----------------------------------------------
def test_part1_contractor_email_sender(admin_headers):
    r = requests.get(f"{BASE_URL}/api/twilio/contractor/emails", headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("sender_email") == "info@bidvex.com"
    assert d.get("sender_name") == "BidVex Canada"
    assert d.get("support_phone") == "+1 450 634 3099"


# --- PART 2 PUBLIC: list + detail + 404 -------------------------------------
def test_public_jobs_list_only_active():
    r = requests.get(f"{BASE_URL}/api/careers/jobs", timeout=20)
    assert r.status_code == 200
    body = r.json()
    items = body.get("items", body.get("jobs", body))
    assert isinstance(items, list)
    assert len(items) >= 2
    ids = [j["id"] for j in items]
    assert JOB_ID in ids and JOB2_ID in ids
    cache = r.headers.get("cache-control", "")
    assert "no-store" in cache or "no-cache" in cache, cache


def test_public_job_detail_ok():
    r = requests.get(f"{BASE_URL}/api/careers/jobs/{JOB_ID}", timeout=20)
    assert r.status_code == 200
    assert r.json()["id"] == JOB_ID


def test_public_job_detail_404_unknown():
    r = requests.get(f"{BASE_URL}/api/careers/jobs/does-not-exist-zzz", timeout=20)
    assert r.status_code == 404


# --- PART 2 APPLY: validation errors ----------------------------------------
def _apply(files=None, data=None):
    return requests.post(
        f"{BASE_URL}/api/careers/jobs/{JOB_ID}/apply",
        files=files or {}, data=data or {}, timeout=30,
    )


def _base_form(email="TEST_marc@example.com"):
    return {
        "first_name": "Test",
        "last_name": "Applicant",
        "email": email,
        "phone": "+15145551234",
        "country": "Canada",
        "province": "QC",
        "preferred_language": "en",
    }


def test_apply_invalid_email():
    r = _apply(files={"cv": ("cv.pdf", PDF_BYTES, "application/pdf")},
               data={**_base_form(email="not-an-email")})
    assert r.status_code == 422, r.text
    body = r.json()
    code = (body.get("detail") or {}).get("code") if isinstance(body.get("detail"), dict) else body.get("code")
    assert "invalid_email" in str(body), body


def _full_form(email="TEST_marc@example.com"):
    import json as _json
    d = _base_form(email)
    d["custom_responses"] = _json.dumps({"Years of auction experience": "5+"})
    return d


def test_apply_missing_cv_when_required():
    r = _apply(files={}, data=_full_form())
    assert r.status_code == 422
    assert "cv_required" in str(r.json())


def test_apply_wrong_mime_pdf_lie():
    r = _apply(files={"cv": ("cv.pdf", NOT_PDF_BYTES, "application/pdf")}, data=_full_form())
    assert r.status_code == 422
    assert "invalid_file_type" in str(r.json())


def test_apply_oversize_file():
    big = b"%PDF-1.4\n" + (b"A" * (12 * 1024 * 1024))  # 12MB
    r = _apply(files={"cv": ("cv.pdf", big, "application/pdf")}, data=_full_form())
    assert r.status_code == 422
    assert "file_too_large" in str(r.json())


def test_apply_missing_custom_text_field():
    # JOB_ID requires custom text field 'Years of auction experience' — omit it
    r = _apply(files={"cv": ("cv.pdf", PDF_BYTES, "application/pdf")}, data=_base_form())
    assert r.status_code == 422
    assert "missing_custom_field" in str(r.json())


def test_apply_success_path():
    import json as _json
    data = _base_form(email="TEST_live_success@example.com")
    data["custom_responses"] = _json.dumps({"Years of auction experience": "5+"})
    r = _apply(files={"cv": ("cv.pdf", PDF_BYTES, "application/pdf")}, data=data)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    assert "applicant_id" in body
    assert "message_en" in body and "message_fr" in body


# --- PART 2 ADMIN: auth, CRUD, attachment path-traversal ---------------------
def test_admin_jobs_requires_admin():
    r = requests.get(f"{BASE_URL}/api/admin/careers/jobs", timeout=20)
    assert r.status_code in (401, 403)


def test_admin_jobs_list(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/careers/jobs", headers=admin_headers, timeout=20)
    assert r.status_code == 200
    items = r.json().get("items", r.json())
    assert isinstance(items, list)


def test_admin_job_crud_lifecycle(admin_headers):
    # Create draft
    r = requests.post(f"{BASE_URL}/api/admin/careers/jobs", headers=admin_headers,
                      json={
                          "title": "TEST_Job_Live",
                          "department": "QA",
                          "description_en": "QA test description",
                          "description_fr": "Description de test QA",
                      }, timeout=20)
    assert r.status_code in (200, 201), r.text
    job = r.json()
    jid = job.get("id") or job.get("job", {}).get("id")
    assert jid
    # PATCH
    r2 = requests.patch(f"{BASE_URL}/api/admin/careers/jobs/{jid}",
                        headers=admin_headers, json={"location": "Remote"}, timeout=20)
    assert r2.status_code == 200, r2.text

    # DELETE while still in draft (no applicants) → succeeds
    r_del = requests.delete(f"{BASE_URL}/api/admin/careers/jobs/{jid}", headers=admin_headers, timeout=20)
    assert r_del.status_code in (200, 204), r_del.text


def test_admin_job_activate_then_archive(admin_headers):
    # Create draft (complete fields so activate succeeds)
    r = requests.post(f"{BASE_URL}/api/admin/careers/jobs", headers=admin_headers,
                      json={
                          "title": "TEST_Job_Activate",
                          "department": "QA",
                          "description_en": "Activate test",
                          "description_fr": "Test d'activation",
                      }, timeout=20)
    assert r.status_code in (200, 201)
    jid = r.json().get("id") or r.json().get("job", {}).get("id")
    r3 = requests.post(f"{BASE_URL}/api/admin/careers/jobs/{jid}/activate", headers=admin_headers, timeout=20)
    assert r3.status_code == 200, r3.text
    r4 = requests.post(f"{BASE_URL}/api/admin/careers/jobs/{jid}/archive", headers=admin_headers, timeout=20)
    assert r4.status_code == 200, r4.text


def test_admin_delete_job_with_applicants_returns_409(admin_headers):
    r = requests.delete(f"{BASE_URL}/api/admin/careers/jobs/{JOB_ID}", headers=admin_headers, timeout=20)
    assert r.status_code == 409
    assert "has_applicants" in str(r.json())


def test_admin_applicants_list_and_status(admin_headers):
    global APPLICANT_ID_SHORTLISTED
    r = requests.get(f"{BASE_URL}/api/admin/careers/applicants", headers=admin_headers, timeout=20)
    assert r.status_code == 200
    items = r.json().get("items", r.json())
    assert isinstance(items, list)
    assert len(items) >= 1
    # Find Marc Tremblay (seeded)
    marc = next((a for a in items if "Tremblay" in (a.get("last_name", "") or "")), items[0])
    aid = marc["id"]
    APPLICANT_ID_SHORTLISTED = aid

    # Status update: shortlisted
    r2 = requests.patch(f"{BASE_URL}/api/admin/careers/applicants/{aid}/status",
                        headers=admin_headers, json={"status": "shortlisted"}, timeout=20)
    assert r2.status_code == 200, r2.text

    # Invalid status
    r3 = requests.patch(f"{BASE_URL}/api/admin/careers/applicants/{aid}/status",
                        headers=admin_headers, json={"status": "bogus_status"}, timeout=20)
    assert r3.status_code == 422


def test_admin_attachment_path_traversal_blocked(admin_headers):
    # Need a valid applicant_id
    r = requests.get(f"{BASE_URL}/api/admin/careers/applicants", headers=admin_headers, timeout=20)
    items = r.json().get("items", [])
    if not items:
        pytest.skip("no applicants")
    aid = items[0]["id"]

    # Try various path traversal patterns
    bad_names = ["foo%2F..%2Fbar", "..hidden", "%2e%2e%2fetc%2fpasswd"]
    for name in bad_names:
        r2 = requests.get(
            f"{BASE_URL}/api/admin/careers/applicants/{aid}/attachments/{name}",
            headers=admin_headers, timeout=20, allow_redirects=False,
        )
        assert r2.status_code in (403, 400, 404), f"{name} → {r2.status_code}"
        # Prefer 403 path_traversal_blocked
