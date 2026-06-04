"""
iter273 — P0 fixes + ROI dashboard verification.

Mission 1 (P0) — Storage facility document 404 recovery:
  • Backend persistent root `/app/uploads/storage_facilities/` is the
    canonical write location.
  • Legacy roots (`uploads/...` + `/app/backend/uploads/...`) stay in
    the read-side candidate list so files uploaded before iter273 are
    still discoverable.
  • NEW endpoint `POST /admin/storage-facilities/{id}/request-resubmission`
    flips the facility back to pending + emails the owner.
  • Frontend `useDocOpener` treats ANY 404 on a storage_facilities path
    as a structured missing-file event, and the modal exposes a
    `request-resubmission-btn` CTA wired to the new endpoint.

Mission 2 (P0) — SIN compliance:
  • TaxInterviewModal no longer renders, validates, or sends a SIN.
  • taxCompliance.js field requirements omit `tax_id` for individuals.
  • Backend `tax-profile` rejects any `sin` / `social_insurance_number` /
    `sin_number` keys with `error_code=sin_not_accepted`.
  • Individual tax-profile updates persist `legal_name` + `date_of_birth`
    + `address` only — no `tax_id` reaches `users.tax_id` from this path.
  • No frontend label string still surfaces SIN to the user.

Mission 3 (feature) — Admin ROI dashboard:
  • AdminExternalCampaigns.jsx mounts a 5-card row at the top of the
    analytics modal: Total Sent, Opens/Clicks, Registrations, Premium
    Upgrades, Fallback Dispatches.
  • Two funnel-rate pills follow: `Click → Registration %` and
    `Registration → Premium Paid %`.
  • Backend `GET /admin/external-campaigns/{id}/analytics` surfaces
    `fallback_dispatches` from `last_dispatch.fallback_used`.
"""
from __future__ import annotations

import os
import re
import asyncio

import httpx
import pytest


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, "..", "frontend", "src"))
BASE = os.environ.get("E2E_BASE_URL", "http://localhost:8001")


def _read(rel: str, root: str = BACKEND_ROOT) -> str:
    with open(os.path.join(root, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _read_fe(rel: str) -> str:
    return _read(rel, root=FRONTEND_ROOT)


def _login_admin():
    try:
        r = httpx.post(
            f"{BASE}/api/auth/login",
            json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
            timeout=8.0,
        )
        if r.status_code != 200:
            return None
        return r.json().get("access_token") or r.json().get("token")
    except Exception:
        return None


# ── Mission 1 — Facility doc 404 recovery ─────────────────────────────


def test_iter273_storage_auctions_defines_persistent_root():
    src = _read("routes/storage_auctions.py")
    assert "FACILITY_DOC_ROOT_PERSISTENT" in src
    assert 'Path("/app/uploads/storage_facilities")' in src
    # Legacy roots still present for read-side discovery.
    assert "FACILITY_DOC_ROOT_REL" in src
    assert "FACILITY_DOC_ROOT_ABS" in src


def test_iter273_upload_writes_to_persistent_then_mirrors_legacy():
    src = _read("routes/storage_auctions.py")
    # Persistent root is mkdir'd + written BEFORE the legacy mirror.
    persistent_idx = src.find("FACILITY_DOC_ROOT_PERSISTENT.mkdir")
    legacy_mirror_idx = src.find("[facility-doc-upload] legacy mirror skipped")
    assert 0 < persistent_idx < legacy_mirror_idx, (
        "persistent write must precede the legacy mirror block"
    )


def test_iter273_serve_endpoint_searches_persistent_first():
    src = _read("routes/storage_auctions.py")
    candidates_block = src[src.find("candidates = ["):src.find("found = next")]
    assert "FACILITY_DOC_ROOT_PERSISTENT / bare" in candidates_block
    # And persistent must be the FIRST candidate (highest priority).
    persistent_pos = candidates_block.find("FACILITY_DOC_ROOT_PERSISTENT / bare")
    legacy_pos = candidates_block.find("FACILITY_DOC_ROOT_REL / bare")
    abs_pos = candidates_block.find("FACILITY_DOC_ROOT_ABS / bare")
    assert 0 <= persistent_pos < legacy_pos
    assert 0 <= persistent_pos < abs_pos


def test_iter273_resubmission_endpoint_registered():
    src = _read("routes/storage_auctions.py")
    assert '@storage_router.post("/admin/storage-facilities/{facility_id}/request-resubmission")' in src
    assert "async def admin_request_facility_resubmission" in src
    # Must reset verification flag + stamp metadata.
    assert '"company_registration_verified": False' in src
    assert "company_registration_resubmission_requested_at" in src
    # Must fire the rejection-style email so the owner knows to re-upload.
    assert "send_storage_facility_registration_rejected_email" in src


def test_iter273_resubmission_endpoint_responds_to_unknown_facility():
    """Live: hitting the endpoint with a bogus facility id must return
    a clean 404 with detail message — not crash with 500."""
    token = _login_admin()
    if not token:
        pytest.skip("admin login unavailable")
    r = httpx.post(
        f"{BASE}/api/admin/storage-facilities/does-not-exist/request-resubmission",
        json={},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    assert r.status_code == 404


def test_iter273_resubmission_endpoint_works_on_real_facility():
    """End-to-end: locate an existing facility (any of them), call
    request-resubmission, verify the response shape + DB stamp + the
    facility's `company_registration_verified` flag drops to False."""
    token = _login_admin()
    if not token:
        pytest.skip("admin login unavailable")
    r = httpx.get(
        f"{BASE}/api/admin/storage-facilities",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    if r.status_code != 200:
        pytest.skip("no admin facilities endpoint access")
    payload = r.json() or {}
    facilities = payload.get("facilities") if isinstance(payload, dict) else payload
    if not facilities:
        pytest.skip("no facility documents to exercise the flow on")

    facility = facilities[0]
    fid = facility["id"]

    r2 = httpx.post(
        f"{BASE}/api/admin/storage-facilities/{fid}/request-resubmission",
        json={},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["success"] is True
    assert body["facility_id"] == fid
    assert "requested_at" in body
    # `email_sent` may be False if SendGrid is throttled — but the key
    # must always be present as a boolean.
    assert isinstance(body.get("email_sent"), bool)
    # Bilingual confirmation strings.
    assert "Resubmission request sent" in body["message_en"]
    assert "Demande de soumission envoyée" in body["message_fr"]


def test_iter273_frontend_useDocOpener_falls_back_on_storage_facility_404():
    """The hook must trigger the missing-doc modal even when the 404
    envelope is missing `error_code` (e.g. ingress 404 layer)."""
    src = _read_fe("pages/admin/AdminFacilities.js")
    # Defensive `typeof === 'object'` guard so a string detail doesn't
    # break `.error_code` lookups.
    assert "typeof data.detail === 'object'" in src
    # The structural fallback heuristic.
    assert "isStorageFacilityDoc" in src
    assert "/storage_facilities/" in src
    # Facility id passthrough so the modal can fire the resubmission CTA.
    assert "facility_id:  facility?.id" in src


def test_iter273_missing_doc_modal_has_request_resubmission_button():
    src = _read_fe("pages/admin/AdminFacilities.js")
    assert 'data-testid="request-resubmission-btn"' in src
    assert "requestResubmission" in src
    # Wired to the new backend endpoint.
    assert "/admin/storage-facilities/${missingDocModal.facility_id}/request-resubmission" in src


def test_iter273_view_button_passes_facility_into_doc_opener():
    src = _read_fe("pages/admin/AdminFacilities.js")
    # The onClick must pass BOTH the URL AND the facility object.
    assert "openDoc(f.company_registration_document_url, f)" in src


# ── Mission 2 — SIN compliance ────────────────────────────────────────


def _strip_js_comments(src: str) -> str:
    """Remove JS comments (// and /* ... */) so test assertions can
    look for user-facing literal strings without false positives from
    iter273 explanatory comments that intentionally reference SIN."""
    # Remove /* ... */ block comments first.
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    # Then strip // line comments to end-of-line.
    src = re.sub(r"//[^\n]*", "", src)
    return src


def test_iter273_tax_modal_no_sin_input_or_validator():
    src = _strip_js_comments(_read_fe("components/TaxInterviewModal.js"))
    # No literal SIN keys/labels left for users (comments are stripped).
    assert "Social Insurance Number" not in src
    assert "Numéro d\\'Assurance Sociale" not in src
    assert "NAS requis" not in src
    assert "SIN required" not in src
    assert "SIN must be 9 digits" not in src
    # The form state no longer carries a `sin` field.
    assert "sin: ''" not in src
    assert "formData.sin" not in src
    # The submit payload no longer includes tax_id for individuals.
    individual_payload_block = src[src.find("sellerType === 'individual'") : ]
    assert "tax_id: formData.sin" not in individual_payload_block


def test_iter273_tax_compliance_helper_drops_sin_label_for_individuals():
    src = _read_fe("utils/taxCompliance.js")
    # Individual required-fields no longer contain `tax_id`.
    individual_block = src[src.find("individual: {"):src.find("business: {")]
    assert "'tax_id'" not in individual_block
    # And the user-facing label string is gone.
    assert "Social Insurance Number (SIN)" not in src
    assert "Numéro d'assurance sociale (NAS)" not in src
    # Declarations text now affirms the no-SIN policy.
    assert "BidVex never requests or stores a Social Insurance Number" in src
    assert "ne demande ni ne stocke jamais de numéro d'assurance sociale" in src


def test_iter273_backend_tax_profile_rejects_sin_keys():
    src = _read("routes/profiles.py")
    # Forbidden-key rejection block.
    assert '"sin", "social_insurance_number", "sin_number"' in src
    assert '"error_code": "sin_not_accepted"' in src
    # Individual branch silently drops any incoming `tax_id`.
    assert 'tax_data.pop("tax_id", None)' in src
    # update_data block does NOT persist tax_id on the individual branch.
    individual_branch = src[
        src.find('if seller_type == "individual":', src.find("update_data = {")):
        src.find("else:", src.find('"tax_onboarding_completed": True,'))
    ]
    assert '"tax_id":' not in individual_branch


def test_iter273_backend_tax_profile_live_rejects_sin_field():
    """Live HTTP: posting a payload that includes `sin` for an individual
    seller must come back as a 400 with the structured error code."""
    token = _login_admin()
    if not token:
        pytest.skip("admin login unavailable")
    r = httpx.put(
        f"{BASE}/api/users/me/tax-profile",
        json={
            "seller_type": "individual",
            "sin":         "123456789",
            "date_of_birth": "1990-01-01",
            "address":     "123 Test Street",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    assert r.status_code == 400, r.text
    detail = r.json().get("detail") or {}
    assert detail.get("error_code") == "sin_not_accepted"
    assert "Social Insurance Number" in detail.get("message_en", "")


def test_iter273_no_orphan_sin_references_in_user_facing_strings():
    """Sweep the user-facing components for any remaining literal
    'SIN' / 'Social Insurance Number' / 'NAS' strings that would
    surface to a customer. Anti-fraud rules referencing prohibited SIN
    cards on the marketplace are intentionally exempted. Code comments
    (which explain the iter273 policy change) are stripped before
    matching."""
    user_facing_files = [
        "components/TaxInterviewModal.js",
        "utils/taxCompliance.js",
    ]
    forbidden_phrases = [
        "Social Insurance Number (SIN)",
        "Numéro d'assurance sociale (NAS)",
        "SIN required",
        "NAS requis",
        "SIN is required",
        "Enter your SIN",
        "Saisissez votre NAS",
    ]
    for rel in user_facing_files:
        src = _strip_js_comments(_read_fe(rel))
        for phrase in forbidden_phrases:
            assert phrase not in src, f"{rel} still contains: {phrase!r}"


def test_iter273_user_payload_individual_does_not_carry_sin_or_tax_id():
    """Static check: the modal's submit payload for individual sellers
    persists only the four non-SIN fields."""
    src = _read_fe("components/TaxInterviewModal.js")
    payload_section = src[src.find("const payload = {"):src.find("    };", src.find("const payload = {"))]
    # iter273 marker comment present.
    assert "iter273" in payload_section
    # No `sin` and no `tax_id` on the individual branch.
    assert "formData.sin" not in payload_section
    # Required positive fields ARE present.
    assert "legal_name: formData.legal_name" in payload_section
    assert "date_of_birth: formData.date_of_birth" in payload_section
    assert "address: formData.principal_address" in payload_section


# ── Mission 3 — Admin ROI dashboard ───────────────────────────────────


def test_iter273_admin_external_campaigns_renders_5_roi_cards():
    src = _read_fe("pages/admin/AdminExternalCampaigns.jsx")
    assert 'data-testid="roi-cards-row"' in src
    # The 5 keys live in the `roiCards` array — testid attrs are built
    # at render via `roi-card-${c.key}` template literals.
    for key in (
        "total-sent",
        "opens-clicks",
        "registrations",
        "premium-upgrades",
        "fallback-dispatches",
    ):
        assert f"key:   '{key}'," in src, f"missing ROI card key: {key}"
    # The template literal that wires the key into the test id must exist.
    assert "data-testid={`roi-card-${c.key}`}" in src
    assert "data-testid={`roi-value-${c.key}`}" in src


def test_iter273_admin_dashboard_exposes_conversion_rate_pills():
    src = _read_fe("pages/admin/AdminExternalCampaigns.jsx")
    assert 'data-testid="roi-funnel-rates"' in src
    assert 'data-testid="rate-click-to-reg"' in src
    assert 'data-testid="rate-reg-to-premium"' in src
    # Defensive divide-by-zero helper.
    assert "_safePct" in src


def test_iter273_admin_dashboard_reads_fallback_count_from_payload():
    src = _read_fe("pages/admin/AdminExternalCampaigns.jsx")
    # Must accept either the named key or the legacy alias.
    assert "data.fallback_dispatches ?? data.fallback_used" in src


def test_iter273_backend_analytics_endpoint_surfaces_fallback_dispatches():
    src = _read("routes/external_campaigns.py")
    assert '"fallback_dispatches"' in src
    # Read straight from the `last_dispatch.fallback_used` integer.
    assert "last_dispatch.get(\"fallback_used\")" in src
    # AND the full envelope is echoed back for diagnostics.
    assert 'a["last_dispatch"] = last_dispatch' in src


def test_iter273_analytics_endpoint_returns_zero_safe_defaults_live():
    """End-to-end: a freshly created (not-yet-sent) campaign should
    return zeros for every ROI counter, never null/missing keys."""
    token = _login_admin()
    if not token:
        pytest.skip("admin login unavailable")

    import uuid
    payload = {
        "name":         f"iter273-roi-{uuid.uuid4().hex[:6]}",
        "subject_en":   "Test ROI subject",
        "subject_fr":   "Test ROI sujet",
        "body_html_en": "<p>Test {unsubscribe_url}</p>",
        "body_html_fr": "<p>Test FR</p>",
    }
    r = httpx.post(
        f"{BASE}/api/admin/external-campaigns",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    assert r.status_code == 200, r.text
    cid = r.json()["campaign_id"]
    try:
        r2 = httpx.get(
            f"{BASE}/api/admin/external-campaigns/{cid}/analytics",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        assert r2.status_code == 200, r2.text
        a = r2.json()
        for k in (
            "delivered", "opened", "clicked",
            "registrations", "premium_upgrades", "fallback_dispatches",
        ):
            assert k in a, f"analytics envelope missing {k}"
            assert a[k] == 0, f"{k} must default to 0 on a fresh campaign, got {a[k]}"
    finally:
        httpx.delete(
            f"{BASE}/api/admin/external-campaigns/{cid}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
