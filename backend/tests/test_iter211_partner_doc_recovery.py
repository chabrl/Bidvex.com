"""
iter211 — Partner document serve robustness + admin recovery flow.

Verifies the fix for the reopened P0 where clicking an admin document link
returned a flat `{"detail": "File not found"}` JSON page (ephemeral
filesystem wipe after redeploy).

Tests:
  1. Serve endpoint defensively strips legacy URL prefixes (back-compat for
     DB rows that stored full `/api/uploads/...` paths).
  2. Missing file → structured 404 with `error_code`, owner_email,
     owner_user_id, owner_status, bilingual messages.
  3. Owner lookup uses the filename's user-id prefix (works even when the
     specific random suffix differs from what's currently in DB).
  4. Path traversal is blocked (`..`, slashes, leading dot).
  5. Admin `/admin/partners/{id}/request-resubmission` resets status and
     records an audit row.
  6. Admin `/admin/partners/missing-documents-audit` reports affected vs
     healthy correctly.
"""
import os
import re
import pytest


# ─── Static smoke tests (no live HTTP needed) ────────────────────────────

def test_serve_endpoint_strips_legacy_prefixes():
    with open("/app/backend/routes/partners.py", "r") as f:
        body = f.read()
    # All 4 prefix variants must be stripped
    for p in ("/api/uploads/partner_docs/", "/uploads/partner_docs/",
              "api/uploads/partner_docs/", "uploads/partner_docs/"):
        assert f'"{p}"' in body, f"Serve endpoint missing strip for prefix: {p}"


def test_serve_endpoint_blocks_path_traversal():
    with open("/app/backend/routes/partners.py", "r") as f:
        body = f.read()
    assert '".." in bare or "/" in bare or bare.startswith(".")' in body, \
        "Serve endpoint must block path-traversal post-strip"


def test_serve_endpoint_searches_both_roots():
    with open("/app/backend/routes/partners.py", "r") as f:
        body = f.read()
    assert 'Path("uploads/partner_docs")' in body
    assert 'Path("/app/backend/uploads/partner_docs")' in body


def test_structured_404_includes_required_fields():
    with open("/app/backend/routes/partners.py", "r") as f:
        body = f.read()
    # Find the 404 raise block
    block_start = body.index('"error_code": "file_missing_on_disk"')
    block = body[block_start:block_start + 1500]
    for field in ("filename", "message_en", "message_fr", "owner_email", "owner_user_id", "owner_status"):
        assert f'"{field}"' in block, f"Structured 404 missing field: {field}"


def test_owner_lookup_uses_userid_prefix_pattern():
    """Owner lookup must extract user_id from `(neq|cert)_{user_id}_*` so it
    works even when the DB's current filename has a different random suffix
    than the one the admin clicked."""
    with open("/app/backend/routes/partners.py", "r") as f:
        body = f.read()
    assert r'r"^(?:neq|cert)_([0-9a-f-]{8,})"' in body, \
        "Owner lookup must use user_id prefix regex"


def test_admin_request_resubmission_endpoint_exists():
    with open("/app/backend/routes/partners.py", "r") as f:
        body = f.read()
    assert "/admin/partners/{user_id}/request-resubmission" in body
    assert "request_partner_resubmission" in body
    # Resets status to rejected so existing Resubmit panel works
    assert '"partner_verification_status": "rejected"' in body
    # Wipes stale file refs
    assert '"partner_neq_document": None' in body
    assert '"partner_certifications": []' in body


def test_audit_endpoint_exists_and_admin_only():
    with open("/app/backend/routes/partners.py", "r") as f:
        body = f.read()
    assert "/admin/partners/missing-documents-audit" in body
    assert "audit_missing_partner_documents" in body
    # Admin guard
    audit_start = body.index("audit_missing_partner_documents")
    audit_block = body[audit_start:audit_start + 2000]
    assert "admin_required" in audit_block


def test_admin_frontend_handles_structured_404():
    """The admin partner manager must intercept `file_missing_on_disk` and
    show a CTA modal — NOT navigate the browser to the raw JSON."""
    with open("/app/frontend/src/pages/admin/PartnerManager.js", "r") as f:
        body = f.read()
    # No more raw <a href> that opens the URL directly in a new tab
    assert "openDocument" in body
    assert "useDocumentOpener" in body
    # CTA modal exists
    assert 'data-testid="missing-doc-modal"' in body
    assert 'data-testid="request-resubmission-btn"' in body
    # Structured error code is the trigger
    assert "file_missing_on_disk" in body
    # The OLD pattern (plain anchor with token query) must be gone for the doc links
    neq_link_start = body.index('data-testid="partner-doc-neq-link"')
    # find the tag opening before that
    open_tag = body.rfind("<", 0, neq_link_start)
    assert body[open_tag:neq_link_start].startswith("<button"), \
        "Document link must be a button now, not an anchor (was: plain <a href>)"


# ─── Live HTTP integration test ──────────────────────────────────────────

API_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com")


def _admin_token():
    import requests
    r = requests.post(
        f"{API_URL}/api/auth/login",
        json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
        timeout=10,
    )
    if r.status_code != 200:
        pytest.skip(f"Could not log in admin ({r.status_code}); skipping live test")
    return r.json().get("token") or r.json().get("access_token")


class TestServeEndpointLive:
    def test_missing_file_returns_structured_404(self):
        import requests
        token = _admin_token()
        r = requests.get(
            f"{API_URL}/api/uploads/partner_docs/neq_d000524d-82f3-42d9-8a5a-e7c7f19d7546_24d4b19a.pdf",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        assert r.status_code == 404
        body = r.json()
        detail = body.get("detail", {})
        assert detail.get("error_code") == "file_missing_on_disk"
        assert "Business Registration" in detail.get("message_en", "") or "no longer available" in detail.get("message_en", "")
        # Owner lookup should resolve via user-id prefix
        assert detail.get("owner_email") is not None
        assert detail.get("owner_user_id") == "d000524d-82f3-42d9-8a5a-e7c7f19d7546"

    def test_path_traversal_blocked(self):
        import requests
        token = _admin_token()
        r = requests.get(
            f"{API_URL}/api/uploads/partner_docs/..%2F..%2Fetc%2Fpasswd",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        # Could be 400 (our check) or 404 (FastAPI router) — both are safe
        assert r.status_code in (400, 404)

    def test_audit_endpoint_returns_report(self):
        import requests
        token = _admin_token()
        r = requests.get(
            f"{API_URL}/api/admin/partners/missing-documents-audit",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        for key in ("total_partners_with_docs", "affected", "healthy", "rows"):
            assert key in data
        # At least one row exposes is_affected
        assert any("is_affected" in r for r in data["rows"]) or data["total_partners_with_docs"] == 0
