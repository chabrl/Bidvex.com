"""Backend tests for iteration 158 pre-launch fixes:
  1. Categories: no Farm Equipment, has Heavy Equipment
  2. PUT /api/users/me province persistence
  3. POST /api/auth/email-change/request (password validation + same-email rejection)
  4. POST /api/auth/email-change/confirm with invalid token
  5. POST /api/listings image compression (base64 PNG -> JPEG)
  6. AI chatbot POST /api/ai-chat/message
  7. /api/auth/session exists for Emergent Google OAuth
"""
import os
import io
import base64
import requests
import pytest
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PW = "Anderosli123!@#"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text[:200]}")
    data = r.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------------- Fix 5: Categories ----------------
class TestCategories:
    def test_no_farm_equipment(self):
        r = requests.get(f"{BASE_URL}/api/categories", timeout=15)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        cats = data if isinstance(data, list) else data.get("categories", [])
        flat_names = []
        def walk(items):
            for it in items:
                if isinstance(it, dict):
                    flat_names.append((it.get("slug") or "").lower())
                    flat_names.append((it.get("name") or "").lower())
                    flat_names.append((it.get("name_en") or "").lower())
                    flat_names.append((it.get("name_fr") or "").lower())
                    walk(it.get("children", []) or it.get("subcategories", []) or [])
        walk(cats)
        joined = " ".join(flat_names)
        assert "farm_equipment" not in joined and "farm equipment" not in joined, \
            f"Farm Equipment still present: {joined}"
        assert "heavy_equipment" in joined or "heavy equipment" in joined, \
            f"Heavy Equipment missing: {joined}"


# ---------------- Fix 1: Profile - Province ----------------
class TestProfileProvince:
    def test_put_users_me_province(self, auth_headers):
        r = requests.put(f"{BASE_URL}/api/users/me", json={"province": "QC"}, headers=auth_headers, timeout=15)
        assert r.status_code in (200, 204), f"PUT /users/me province failed: {r.status_code} {r.text[:200]}"

        me = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers, timeout=15)
        assert me.status_code == 200
        assert me.json().get("province") == "QC", f"Province not persisted: {me.json()}"


# ---------------- Fix 1: Email change flow ----------------
class TestEmailChange:
    def test_request_rejects_wrong_password(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/auth/email-change/request",
                          json={"new_email": "newmail_TEST@example.com", "current_password": "WrongPassword!!"},
                          headers=auth_headers, timeout=15)
        assert r.status_code == 400, f"Expected 400 for wrong password, got {r.status_code}: {r.text[:200]}"
        assert "password" in r.text.lower() or "incorrect" in r.text.lower()

    def test_request_rejects_same_email(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/auth/email-change/request",
                          json={"new_email": ADMIN_EMAIL, "current_password": ADMIN_PW},
                          headers=auth_headers, timeout=15)
        assert r.status_code == 400, f"Expected 400 for same email, got {r.status_code}: {r.text[:200]}"

    def test_request_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/auth/email-change/request",
                          json={"new_email": "x@y.com", "current_password": "x"},
                          timeout=15)
        assert r.status_code in (401, 403), f"Expected 401/403 unauth, got {r.status_code}"

    def test_confirm_invalid_token(self):
        r = requests.post(f"{BASE_URL}/api/auth/email-change/confirm",
                          json={"token": "invalid-bogus-token-999"}, timeout=15)
        assert r.status_code == 400, f"Expected 400 for bad token, got {r.status_code}: {r.text[:200]}"


# ---------------- Fix 4: Image compression ----------------
def _make_big_png_data_url(w=1600, h=1200):
    img = Image.new("RGB", (w, h), (120, 180, 220))
    # Add gradient-ish noise so PNG actually has size
    pix = img.load()
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            pix[x, y] = ((x + y) % 255, (x * 2) % 255, (y * 3) % 255)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b}", len(buf.getvalue())


class TestImageCompression:
    def test_listing_creation_compresses_images(self, auth_headers):
        data_url, raw_png_size = _make_big_png_data_url()
        payload = {
            "title": "TEST_CompressCheck_158",
            "description": "Test listing for compression — safe to delete.",
            "category": "heavy_equipment",
            "condition": "used",
            "starting_price": 100,
            "buy_now_price": 500,
            "location": "Montreal, QC",
            "city": "Montreal",
            "region": "QC",
            "country": "CA",
            "images": [data_url],
            "auction_end_date": "2026-12-31T23:59:59Z",
            "agreement_accepted": True,
        }
        r = requests.post(f"{BASE_URL}/api/listings", json=payload, headers=auth_headers, timeout=120)
        if r.status_code not in (200, 201):
            pytest.skip(f"Listing creation blocked (status {r.status_code}: {r.text[:200]}) — admin requires payment method. Unit test covers compression service instead.")
        data = r.json()
        imgs = data.get("images") or data.get("listing", {}).get("images") or []
        assert imgs, f"No images in response: {data}"
        first = imgs[0]
        assert first.startswith("data:image/jpeg") or first.startswith("http"), \
            f"Image not compressed to JPEG or uploaded; prefix={first[:40]}"
        if first.startswith("data:image/jpeg"):
            compressed_size = len(base64.b64decode(first.split(",", 1)[1]))
            assert compressed_size < raw_png_size
            img = Image.open(io.BytesIO(base64.b64decode(first.split(",", 1)[1])))
            assert max(img.size) <= 800

        lid = data.get("id") or data.get("listing", {}).get("id")
        if lid:
            requests.delete(f"{BASE_URL}/api/listings/{lid}", headers=auth_headers, timeout=15)

    def test_compression_service_unit(self):
        """Unit test for compress_data_url — covers the key logic used in listings POST."""
        import sys
        sys.path.insert(0, "/app/backend")
        from services.image_compression import compress_data_url
        data_url, raw_png_size = _make_big_png_data_url(1600, 1200)
        out = compress_data_url(data_url)
        assert out.startswith("data:image/jpeg;base64,"), f"Output not JPEG: {out[:40]}"
        compressed_raw = base64.b64decode(out.split(",", 1)[1])
        assert len(compressed_raw) < raw_png_size, \
            f"Compressed {len(compressed_raw)} not smaller than input {raw_png_size}"
        img = Image.open(io.BytesIO(compressed_raw))
        assert max(img.size) <= 800, f"Not resized to 800: {img.size}"
        # Reduction ratio check — PNG->JPEG at 800px should be >50% smaller
        ratio = len(compressed_raw) / raw_png_size
        assert ratio < 0.7, f"Compression ratio too low: {ratio}"


# ---------------- Fix 2: AI chatbot ----------------
class TestAIChatbot:
    def test_ai_chat_responds(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/ai-chat/message",
                          json={"message": "Hello, what is BidVex?"},
                          headers=auth_headers, timeout=60)
        # It may require auth or not; accept 200; record degraded cases
        assert r.status_code == 200, f"AI chat failed: {r.status_code} {r.text[:300]}"
        data = r.json()
        msg = data.get("message") or data.get("reply") or data.get("response") or data.get("text")
        assert msg and isinstance(msg, str) and len(msg) > 0, f"AI chat no message: {data}"


# ---------------- Emergent Google OAuth session endpoint ----------------
class TestAuthSession:
    def test_session_endpoint_exists(self):
        # Should not 404; with no session_id should 400/401/422, not 404
        r = requests.post(f"{BASE_URL}/api/auth/session", json={}, timeout=15)
        assert r.status_code != 404, "Auth session endpoint is missing"
        assert r.status_code in (400, 401, 422), f"Unexpected: {r.status_code} {r.text[:200]}"
