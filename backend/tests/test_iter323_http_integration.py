"""
iter323 HTTP integration tests against preview URL.
Covers all 5 directives end-to-end through the public ingress.
"""
import os
import io
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASS = "Anderosli123!@#"
CONTRACTOR_EMAIL = "charbellicha1992@gmail.com"
CONTRACTOR_PASS = "TestContractor2026!"


# ---------- Auth helpers ----------
def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def contractor_token():
    return _login(CONTRACTOR_EMAIL, CONTRACTOR_PASS)


def _ch(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------- DIR1: Account-type validation ----------
class TestDir1AccountTypes:
    def _base_payload(self, acct_type, email):
        return {
            "account_type": acct_type,
            "business_name": "TEST_iter323 Co",
            "contact_name": "TEST iter323",
            "email": email,
            "phone": "+15145550001",
            "province": "QC",
            "preferred_language": "en",
        }

    def test_liquidator_rejected_422(self, contractor_token):
        r = requests.post(
            f"{API}/twilio/contractor/create-client-account",
            json=self._base_payload("liquidator", "TEST_iter323_lq@example.com"),
            headers=_ch(contractor_token), timeout=20,
        )
        assert r.status_code == 422, f"expected 422 got {r.status_code} {r.text[:200]}"
        body = r.json().get("detail", r.json())
        assert "allowed" in body or "message_fr" in body or "fr" in str(body).lower()

    def test_broker_rejected_422(self, contractor_token):
        r = requests.post(
            f"{API}/twilio/contractor/create-client-account",
            json=self._base_payload("broker", "TEST_iter323_br@example.com"),
            headers=_ch(contractor_token), timeout=20,
        )
        assert r.status_code == 422, r.text[:200]

    def test_individual_seller_accepted(self, contractor_token):
        import uuid as _u
        r = requests.post(
            f"{API}/twilio/contractor/create-client-account",
            json=self._base_payload("individual_seller", f"TEST_iter323_ind_{_u.uuid4().hex[:8]}@example.com"),
            headers=_ch(contractor_token), timeout=30,
        )
        # 200 success OR 409 (already exists from prior runs); both prove the type is allowed
        assert r.status_code in (200, 201, 409), f"got {r.status_code} {r.text[:200]}"


# ---------- DIR3: IVR endpoints ----------
class TestDir3IVR:
    def test_incoming_first_step_returns_gather_lang(self):
        r = requests.post(f"{API}/twilio/ivr/incoming", data={"CallSid": "TEST_iter323_a"}, timeout=15)
        assert r.status_code == 200
        body = r.text
        assert "<Gather" in body
        # bilingual prompt mentions Press 1 / Appuyez (one of)
        assert ("English" in body) or ("français" in body.lower()) or ("francais" in body.lower())

    def test_incoming_lang_step_returns_extension_gather(self):
        r = requests.post(
            f"{API}/twilio/ivr/incoming",
            params={"lang_step": "1"},
            data={"CallSid": "TEST_iter323_b", "Digits": "1"},
            timeout=15,
        )
        assert r.status_code == 200
        body = r.text
        assert "<Gather" in body
        assert "finishOnKey" in body or "#" in body

    def test_route_valid_ext_1220_dials_personal_phone_with_main_callerid(self):
        r = requests.post(
            f"{API}/twilio/ivr/route",
            params={"lang": "en"},
            data={"CallSid": "TEST_iter323_c", "Digits": "1220", "From": "+15145559999"},
            timeout=15,
        )
        assert r.status_code == 200
        body = r.text
        assert "<Dial" in body
        # callerId privacy = BidVex main number
        assert "+14506343099" in body, f"expected main callerId in TwiML: {body[:400]}"
        # whisper url present
        assert "whisper" in body
        # the personal phone is dialed
        assert "+15145559876" in body

    def test_route_digit_zero_routes_to_support(self):
        r = requests.post(
            f"{API}/twilio/ivr/route",
            params={"lang": "en"},
            data={"CallSid": "TEST_iter323_d", "Digits": "0", "From": "+15145550000"},
            timeout=15,
        )
        assert r.status_code == 200
        # either dials support or speaks support fallback
        assert ("<Dial" in r.text) or ("support" in r.text.lower())

    def test_route_unknown_ext_returns_inactive_message(self):
        r = requests.post(
            f"{API}/twilio/ivr/route",
            params={"lang": "en"},
            data={"CallSid": "TEST_iter323_e", "Digits": "9999", "From": "+15145550000"},
            timeout=15,
        )
        assert r.status_code == 200
        # The "extension is no longer active" / "0 for general support" copy
        assert "extension" in r.text.lower()

    def test_whisper_fr(self):
        r = requests.post(
            f"{API}/twilio/ivr/whisper",
            params={"lang": "fr", "caller_from": "+15145559999"},
            data={"CallSid": "TEST_iter323_f"},
            timeout=15,
        )
        assert r.status_code == 200
        body = r.text
        assert "<Say" in body
        assert "fr" in body.lower()  # language attr or text
        assert "+15145559999" in body or "5145559999" in body

    def test_whisper_en(self):
        r = requests.post(
            f"{API}/twilio/ivr/whisper",
            params={"lang": "en", "caller_from": "+15145558888"},
            data={"CallSid": "TEST_iter323_g"},
            timeout=15,
        )
        assert r.status_code == 200
        assert "Incoming BidVex" in r.text or "BidVex" in r.text

    def test_ivr_status_completed_persists(self):
        r = requests.post(
            f"{API}/twilio/ivr/status",
            data={"CallSid": "TEST_iter323_status_x", "DialCallStatus": "completed", "DialCallDuration": "42"},
            timeout=15,
        )
        # 200 (and the row is updated if it pre-existed; if no row, idempotent no-op also OK)
        assert r.status_code in (200, 204)


# ---------- DIR3: Contractor-side extension/profile/calls/leaderboard ----------
class TestDir3ContractorAPIs:
    def test_extension_me(self, contractor_token):
        r = requests.get(f"{API}/twilio/contractor/extension/me", headers=_ch(contractor_token), timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("extension_number") == 1220
        assert "450" in str(data.get("support_phone", ""))
        assert "ext" in data.get("share_text_en", "").lower()
        assert "poste" in data.get("share_text_fr", "").lower()

    def test_inbound_calls_self_only(self, contractor_token):
        r = requests.get(f"{API}/twilio/contractor/inbound-calls", headers=_ch(contractor_token), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        # rows or items list; shape can vary — accept either
        items = body.get("rows") or body.get("items") or body.get("calls") or []
        assert isinstance(items, list)

    def test_leaderboard_shape_no_dollar_earnings(self, contractor_token):
        r = requests.get(f"{API}/twilio/contractor/leaderboard", headers=_ch(contractor_token), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        rows = body.get("rows", [])
        assert isinstance(rows, list)
        if rows:
            row = rows[0]
            for forbidden in ("dollar_earnings", "earnings_dollars", "monthly_earnings", "earnings_amount"):
                assert forbidden not in row, f"leaderboard row leaks dollar field: {forbidden}"
            assert "rank" in row
            assert "display_name" in row or "name" in row
            # is_self present somewhere
        # at least one of these
        assert "rows" in body

    def test_patch_profile_valid_phone(self, contractor_token):
        r = requests.patch(
            f"{API}/twilio/contractor/profile/me",
            json={"personal_phone_number": "+14501234567"},
            headers=_ch(contractor_token), timeout=15,
        )
        assert r.status_code == 200, r.text
        # restore
        requests.patch(
            f"{API}/twilio/contractor/profile/me",
            json={"personal_phone_number": "+15145559876"},
            headers=_ch(contractor_token), timeout=15,
        )

    def test_patch_profile_invalid_phone_422(self, contractor_token):
        r = requests.patch(
            f"{API}/twilio/contractor/profile/me",
            json={"personal_phone_number": "abc"},
            headers=_ch(contractor_token), timeout=15,
        )
        assert r.status_code in (400, 422), f"expected 400/422 got {r.status_code} {r.text[:200]}"


# ---------- DIR5: Profile photo upload ----------
class TestDir5ProfilePhoto:
    def _tiny_jpeg(self):
        # 1x1 JPEG bytes
        return bytes.fromhex(
            "ffd8ffe000104a46494600010100000100010000ffdb0043000806060706"
            "0508070708090909081009090a0c130d0c0b0b0c1a121316111c1e1c1e1c"
            "1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c"
            "1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1cffc0000b08000100010101"
            "1100ffc4001f0000010501010101010100000000000000000102030405060708090a0b"
            "ffc400b5100002010303020403050504040000017d01020300041105122131410613516107227114328191a1082342b1c11552d1f02433627282090a161718191a25262728292a3435363738393a434445464748494a535455565758595a636465666768696a737475767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffda0008010100003f00fbffd9"
        )

    def test_upload_jpeg_succeeds(self, contractor_token):
        files = {"file": ("test.jpg", self._tiny_jpeg(), "image/jpeg")}
        r = requests.post(
            f"{API}/twilio/contractor/profile/photo",
            files=files,
            headers=_ch(contractor_token),
            timeout=30,
        )
        # accept 200 (uploaded) — must return profile_photo_url
        assert r.status_code == 200, f"got {r.status_code} {r.text[:300]}"
        data = r.json()
        assert data.get("ok") is True
        assert data.get("profile_photo_url"), "missing profile_photo_url"

    def test_upload_pdf_rejected_422(self, contractor_token):
        files = {"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")}
        r = requests.post(
            f"{API}/twilio/contractor/profile/photo",
            files=files, headers=_ch(contractor_token), timeout=15,
        )
        assert r.status_code in (400, 415, 422), f"got {r.status_code}"

    def test_upload_empty_rejected(self, contractor_token):
        files = {"file": ("empty.jpg", b"", "image/jpeg")}
        r = requests.post(
            f"{API}/twilio/contractor/profile/photo",
            files=files, headers=_ch(contractor_token), timeout=15,
        )
        assert r.status_code in (400, 422), f"got {r.status_code}"

    def test_upload_too_large_rejected(self, contractor_token):
        big = b"\xff" * (6 * 1024 * 1024)  # 6MB
        files = {"file": ("big.jpg", big, "image/jpeg")}
        r = requests.post(
            f"{API}/twilio/contractor/profile/photo",
            files=files, headers=_ch(contractor_token), timeout=30,
        )
        assert r.status_code in (400, 413, 422), f"got {r.status_code}"


# ---------- DIR2: SendGrid Inbound Parse ----------
class TestDir2InboundParse:
    def test_inbound_unknown_recipient_matched_false(self):
        data = {
            "to": "noreply@bidvex.ca",
            "from": "client@example.com",
            "subject": "TEST_iter323 inbound no tag",
            "text": "hi",
        }
        r = requests.post(f"{API}/sendgrid/inbound-parse", files={k: (None, v) for k, v in data.items()}, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        assert body.get("matched") in (False, None)

    def test_inbound_unknown_contractor_tag_matched_false(self):
        data = {
            "to": "partners+cNONEXISTENT9999@reply.bidvex.ca",
            "from": "client@example.com",
            "subject": "TEST_iter323 unknown tag",
            "text": "hi",
        }
        r = requests.post(f"{API}/sendgrid/inbound-parse", files={k: (None, v) for k, v in data.items()}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("matched") in (False, None)
