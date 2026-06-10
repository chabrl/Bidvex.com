"""
iter212 — Storage Facility Provincial Business Registration + Access Restriction

Covers:
  • New `company_registration_*` fields on storage_facilities + `StorageFacilityRegister` model
  • `POST /api/storage-facilities/upload-registration-doc` (MIME guard + size + filename)
  • `POST /api/storage-facilities/register` now requires registration trio
  • Admin verify-registration / reject-registration endpoints
  • Listing-creation gate when `company_registration_verified == False`
  • `_require_verified_facility` grandfather behaviour (missing field == legacy verified)
  • Document-serve structured 404 (file_missing_on_disk) + owner/admin perms

Strategy mirrors iter211 test patterns: lightweight static smoke + a handful of
live HTTP tests against the preview env.
"""
import os
import re
import sys
import importlib
import requests

import pytest


# ──────────────────────────────────────────────────────────────────────────
# Static smoke tests (no HTTP, no DB)
# ──────────────────────────────────────────────────────────────────────────


class TestModelExtended:
    """The Pydantic model and the REGISTRATION_TYPES enum must expose the new fields."""

    def test_registration_types_enum_includes_all_provinces(self):
        from models.storage_auction import REGISTRATION_TYPES
        for t in [
            "federal_bn", "qc_neq", "on_ocn", "bc_registry", "ab_corporate",
            "provincial_other", "territorial_other",
        ]:
            assert t in REGISTRATION_TYPES, f"Missing registration type: {t}"

    def test_register_payload_accepts_new_fields(self):
        from models.storage_auction import StorageFacilityRegister
        p = StorageFacilityRegister(
            company_name="Acme Storage",
            contact_name="Joe Owner",
            email="joe@acme.com",
            phone="514-555-1234",
            address="123 Main",
            city="Montreal",
            province="QC",
            postal_code="H1A 1A1",
            accepted_terms=True,
            company_registration_type="qc_neq",
            company_registration_number="1234567890",
            company_registration_document_url="/api/uploads/storage_facilities/reg_x.pdf",
        )
        assert p.company_registration_type == "qc_neq"
        assert p.company_registration_number == "1234567890"
        assert p.company_registration_document_url.endswith(".pdf")

    def test_register_payload_legacy_call_still_loads(self):
        """Pydantic must not break callers that don't pass the new fields yet."""
        from models.storage_auction import StorageFacilityRegister
        p = StorageFacilityRegister(
            company_name="Legacy", contact_name="Jane",
            email="x@y.com", phone="514-555-0000",
            address="123 Main St", city="Quebec", province="QC", postal_code="G1G 1G1",
            accepted_terms=True,
        )
        assert p.company_registration_type is None
        assert p.company_registration_number is None


class TestEndpointsExist:
    """The new routes must be mounted on the FastAPI router."""

    def _routes(self):
        # Importing the server module mounts everything
        if "server" in sys.modules:
            importlib.reload(sys.modules["server"])
        from server import app
        return [r.path for r in app.routes if hasattr(r, "path")]

    def test_upload_endpoint_exists(self):
        assert "/api/storage-facilities/upload-registration-doc" in self._routes()

    def test_serve_endpoint_exists(self):
        assert "/api/uploads/storage_facilities/{filename}" in self._routes()

    def test_verify_registration_endpoint_exists(self):
        assert "/api/admin/storage-facilities/{facility_id}/verify-registration" in self._routes()

    def test_reject_registration_endpoint_exists(self):
        assert "/api/admin/storage-facilities/{facility_id}/reject-registration" in self._routes()


class TestVerifiedFacilityGate:
    """`_require_verified_facility` must block facilities whose registration
    document is not yet verified (explicit False), but must let grandfathered
    legacy facilities pass through (field missing entirely).
    """

    @pytest.mark.asyncio
    async def test_explicit_unverified_registration_blocks_listing(self):
        from routes.storage_auctions import _require_verified_facility
        from fastapi import HTTPException
        import deps as deps_module

            # Stub the DB
        class FakeDB:
            class storage_facilities:
                @staticmethod
                async def find_one(query, projection=None):
                    return {
                        "id": "fac-1",
                        "owner_user_id": "u1",
                        "status": "verified",
                        "company_registration_verified": False,
                    }
        deps_module.set_db(FakeDB())
        from deps import User
        u = User(id="u1", email="x@y.com", name="X")
        with pytest.raises(HTTPException) as exc:
            await _require_verified_facility(u)
        # The new gate raises 403 with the registration-specific error code
        assert exc.value.status_code == 403
        detail = exc.value.detail
        assert isinstance(detail, dict)
        assert detail.get("error") == "company_registration_not_verified"
        assert detail.get("message_en")
        assert detail.get("message_fr")

    @pytest.mark.asyncio
    async def test_grandfathered_facility_with_missing_field_passes(self):
        from routes.storage_auctions import _require_verified_facility
        import deps as deps_module

        class FakeDB:
            class storage_facilities:
                @staticmethod
                async def find_one(query, projection=None):
                    return {
                        "id": "fac-legacy",
                        "owner_user_id": "u-legacy",
                        "status": "verified",
                        # company_registration_verified key intentionally absent
                    }
        deps_module.set_db(FakeDB())
        from deps import User
        u = User(id="u-legacy", email="legacy@x.com", name="Legacy")
        # Should NOT raise — grandfathered
        fac = await _require_verified_facility(u)
        assert fac["id"] == "fac-legacy"

    @pytest.mark.asyncio
    async def test_explicit_true_passes(self):
        from routes.storage_auctions import _require_verified_facility
        import deps as deps_module

        class FakeDB:
            class storage_facilities:
                @staticmethod
                async def find_one(query, projection=None):
                    return {
                        "id": "fac-ok",
                        "owner_user_id": "u-ok",
                        "status": "verified",
                        "company_registration_verified": True,
                    }
        deps_module.set_db(FakeDB())
        from deps import User
        u = User(id="u-ok", email="ok@x.com", name="OK")
        fac = await _require_verified_facility(u)
        assert fac["id"] == "fac-ok"


class TestRegisterValidation:
    """The register endpoint must reject NEW facility submissions that don't
    carry the full registration trio (type + number + document URL).
    """

    @pytest.mark.asyncio
    async def test_invalid_registration_type_returns_400(self):
        from routes.storage_auctions import register_facility
        from models.storage_auction import StorageFacilityRegister
        from fastapi import HTTPException, BackgroundTasks
        import deps as deps_module
        from deps import User

        class FakeDB:
            class storage_facilities:
                @staticmethod
                async def find_one(query, projection=None):
                    return None
                @staticmethod
                async def insert_one(doc):
                    return None
            class users:
                @staticmethod
                async def update_one(*a, **k):
                    return None
        deps_module.set_db(FakeDB())

        payload = StorageFacilityRegister(
            company_name="Bad Reg",
            contact_name="Jane",
            email="bad@x.com",
            phone="555-1234567",
            address="123 Main St",
            city="City",
            province="QC",
            postal_code="H1A 1A1",
            accepted_terms=True,
            company_registration_type="UNKNOWN_BOGUS",   # invalid
            company_registration_number="123",
            company_registration_document_url="/x.pdf",
        )
        u = User(id="u1", email="bad@x.com", name="Bad")
        with pytest.raises(HTTPException) as exc:
            await register_facility(payload, BackgroundTasks(), u)
        assert exc.value.status_code == 400
        assert exc.value.detail["error"] == "invalid_registration_type"

    @pytest.mark.asyncio
    async def test_missing_registration_trio_returns_400(self):
        from routes.storage_auctions import register_facility
        from models.storage_auction import StorageFacilityRegister
        from fastapi import HTTPException, BackgroundTasks
        import deps as deps_module
        from deps import User

        class FakeDB:
            class storage_facilities:
                @staticmethod
                async def find_one(query, projection=None):
                    return None
        deps_module.set_db(FakeDB())

        payload = StorageFacilityRegister(
            company_name="No Reg",
            contact_name="Jane",
            email="noreg@x.com",
            phone="555-1234567",
            address="123 Main St",
            city="City",
            province="QC",
            postal_code="H1A 1A1",
            accepted_terms=True,
            # missing all 3 registration fields
        )
        u = User(id="u2", email="noreg@x.com", name="X")
        with pytest.raises(HTTPException) as exc:
            await register_facility(payload, BackgroundTasks(), u)
        assert exc.value.status_code == 400
        assert exc.value.detail["error"] == "registration_required"
        assert "obligatoire" in exc.value.detail["message_fr"].lower()


class TestAdminEndpoints:
    """Admin verify-registration + reject-registration endpoints."""

    @pytest.mark.asyncio
    async def test_reject_registration_requires_reason(self):
        from routes.storage_auctions import admin_reject_facility_registration
        from fastapi import HTTPException, BackgroundTasks
        import deps as deps_module
        from deps import User

        class FakeDB:
            class storage_facilities:
                @staticmethod
                async def find_one(*a, **k):
                    return {"id": "f1", "email": "f@x.com", "company_name": "F"}
        deps_module.set_db(FakeDB())
        admin = User(id="a1", email="a@x.com", name="Admin", role="admin")
        with pytest.raises(HTTPException) as exc:
            await admin_reject_facility_registration(
                facility_id="f1", payload={}, background_tasks=BackgroundTasks(), current_user=admin,
            )
        assert exc.value.status_code == 400
        assert exc.value.detail["error"] == "reason_required"

    @pytest.mark.asyncio
    async def test_reject_registration_persists_reason(self):
        from routes.storage_auctions import admin_reject_facility_registration
        from fastapi import BackgroundTasks
        import deps as deps_module
        from deps import User

        updates = {}

        class FakeStorageFacilities:
            @staticmethod
            async def find_one(*a, **k):
                return {"id": "f1", "email": "f@x.com", "company_name": "F"}

            @staticmethod
            async def update_one(query, update):
                updates["query"] = query
                updates["set"] = update.get("$set", {})

        class FakeDB:
            storage_facilities = FakeStorageFacilities()

        deps_module.set_db(FakeDB())
        admin = User(id="a1", email="a@x.com", name="Admin", role="admin")
        result = await admin_reject_facility_registration(
            facility_id="f1",
            payload={"reason": "Document is blurry — please rescan."},
            background_tasks=BackgroundTasks(),
            current_user=admin,
        )
        assert result["success"] is True
        assert result["reason"] == "Document is blurry — please rescan."
        assert updates["set"]["company_registration_rejection_reason"] == "Document is blurry — please rescan."
        assert updates["set"]["company_registration_verified"] is False


class TestEmailTemplates:
    """Bilingual EN+FR email helpers must exist + render the reason."""

    @pytest.mark.asyncio
    async def test_rejection_email_helper_includes_reason_and_resubmit_link(self, monkeypatch):
        from services.emails import email_marketplace as en
        captured = {}

        async def fake_send_email(*, to_email, subject, html_content, **kwargs):
            captured.update(to_email=to_email, subject=subject, html=html_content)
            return True

        monkeypatch.setattr(en, "_send_via_unified", fake_send_email)
        ok = await en.send_storage_facility_registration_rejected_email(
            {"email": "f@x.com", "company_name": "Acme"},
            "Document is illegible.",
        )
        assert ok is True
        assert captured["to_email"] == "f@x.com"
        assert "Document is illegible" in captured["html"]
        # Resubmit deep link present
        assert "register-facility?resubmit=1" in captured["html"]
        # Bilingual: both EN and FR words present
        assert "Reason" in captured["html"]
        assert "Motif" in captured["html"]

    @pytest.mark.asyncio
    async def test_verified_email_helper_renders(self, monkeypatch):
        from services.emails import email_marketplace as en
        captured = {}

        async def fake_send_email(*, to_email, subject, html_content, **kwargs):
            captured.update(to_email=to_email, subject=subject, html=html_content)
            return True

        monkeypatch.setattr(en, "_send_via_unified", fake_send_email)
        ok = await en.send_storage_facility_registration_verified_email(
            {"email": "f@x.com", "company_name": "Acme"},
        )
        assert ok is True
        assert "Acme" in captured["html"]
        assert "vérifié" in captured["html"].lower() or "verified" in captured["html"].lower()


# ──────────────────────────────────────────────────────────────────────────
# Live HTTP smoke tests (require preview env up; tolerant of rate limits)
# ──────────────────────────────────────────────────────────────────────────

API_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://prod-verify-2.preview.emergentagent.com",
)


def _login_admin():
    """Best-effort admin login; returns token or None when rate-limited."""
    creds = {"email": "charbel911@gmail.com", "password": "Anderosli123!@#"}
    try:
        r = requests.post(f"{API_URL}/api/auth/login", json=creds, timeout=10)
    except Exception:
        return None
    if r.status_code in (429, 503):
        return None
    if r.status_code != 200:
        return None
    return r.json().get("token") or r.json().get("access_token")


class TestLiveHTTP:
    def test_serve_endpoint_path_traversal_blocked(self):
        token = _login_admin()
        if not token:
            pytest.skip("Admin login unavailable (rate-limited or env missing)")
        # encoded ../etc/passwd attempt
        r = requests.get(
            f"{API_URL}/api/uploads/storage_facilities/..%2F..%2Fetc%2Fpasswd",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        # FastAPI may normalise the path so we accept either 400 or 404,
        # but never 200.
        assert r.status_code in (400, 404)

    def test_serve_endpoint_missing_file_returns_structured_404(self):
        token = _login_admin()
        if not token:
            pytest.skip("Admin login unavailable (rate-limited or env missing)")
        # A fabricated reg_<uuid>_<rand>.pdf that definitely doesn't exist
        bogus = "reg_00000000-0000-0000-0000-000000000000_deadbeef.pdf"
        r = requests.get(
            f"{API_URL}/api/uploads/storage_facilities/{bogus}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        assert r.status_code == 404
        body = r.json()
        detail = body.get("detail") or {}
        assert detail.get("error_code") == "file_missing_on_disk"
        assert "message_en" in detail
        assert "message_fr" in detail

    def test_serve_endpoint_requires_auth(self):
        bogus = "reg_00000000-0000-0000-0000-000000000000_deadbeef.pdf"
        r = requests.get(
            f"{API_URL}/api/uploads/storage_facilities/{bogus}",
            timeout=10,
        )
        assert r.status_code == 401

    def test_admin_list_facilities_shows_grandfather_flag(self):
        """The startup grandfather pass marks legacy facilities. Confirm via
        the admin list endpoint that we expose the new column."""
        token = _login_admin()
        if not token:
            pytest.skip("Admin login unavailable (rate-limited or env missing)")
        r = requests.get(
            f"{API_URL}/api/admin/storage-facilities",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        assert r.status_code == 200
        rows = r.json().get("facilities", [])
        # Should be at least the test facility we inserted previously.
        # We don't assert presence specifically — only that the new keys are
        # available on at least one row (or the table is empty).
        if rows:
            sample = rows[0]
            for key in (
                "company_registration_verified",
            ):
                assert key in sample, f"Missing key on facility row: {key}"
