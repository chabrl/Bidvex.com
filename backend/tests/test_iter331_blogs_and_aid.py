"""
iter331 — Backend test for Press/Blog public+admin CRUD + Contractor Aid Hub (Gemini chat + info).
"""
import os
import io
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
BUYER_EMAIL = "iter331_nonadmin@test.com"
BUYER_PASSWORD = "NonAdmin2026!"

API = f"{BASE_URL}/api"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    assert tok, f"no token in login response: {data}"
    return tok


@pytest.fixture(scope="session")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="session")
def buyer_token():
    try:
        return _login(BUYER_EMAIL, BUYER_PASSWORD)
    except Exception as e:
        pytest.skip(f"buyer login failed: {e}")


def H(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------- Blogs Public ----------

class TestBlogsPublic:
    def test_list_returns_at_least_6_seeded(self):
        r = requests.get(f"{API}/blogs/articles", timeout=20)
        assert r.status_code == 200, r.text
        items = r.json()
        # could be wrapped
        if isinstance(items, dict):
            items = items.get("articles") or items.get("items") or []
        assert isinstance(items, list)
        assert len(items) >= 6, f"expected >=6 seeded articles, got {len(items)}"
        # field shape check
        a = items[0]
        for k in ("slug", "title_en", "title_fr", "excerpt_en", "tag", "read_min"):
            assert k in a, f"missing field {k} in article: {a}"

    def test_get_by_slug_existing(self):
        # use one of the documented seeded slugs
        slug = "how-bidvex-auction-engine-works"
        r = requests.get(f"{API}/blogs/articles/{slug}", timeout=20)
        assert r.status_code == 200, r.text
        a = r.json()
        assert a.get("slug") == slug
        assert a.get("body_en") and isinstance(a["body_en"], str)
        assert a.get("body_fr") and isinstance(a["body_fr"], str)

    def test_get_by_slug_missing_returns_404(self):
        r = requests.get(f"{API}/blogs/articles/does-not-exist-zzz-{uuid.uuid4().hex[:6]}", timeout=20)
        assert r.status_code == 404


# ---------- Blogs Admin CRUD ----------

class TestBlogsAdminCRUD:
    def test_full_round_trip(self, admin_token):
        slug = f"test-iter331-{uuid.uuid4().hex[:8]}"
        payload = {
            "slug": slug,
            "title_en": "TEST iter331 article",
            "title_fr": "TEST iter331 article FR",
            "excerpt_en": "An iter331 test draft.",
            "excerpt_fr": "Un brouillon iter331.",
            "body_en": "# Hello\nBody of test.",
            "body_fr": "# Bonjour\nCorps du test.",
            "tag": "test",
            "read_min": 2,
            "published": False,
        }
        # CREATE draft
        r = requests.post(f"{API}/admin/blogs/articles", json=payload, headers=H(admin_token), timeout=30)
        assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text}"
        created = r.json()
        article_id = created.get("id") or created.get("_id") or created.get("slug")
        assert article_id

        # Public list MUST NOT contain unpublished draft
        pub = requests.get(f"{API}/blogs/articles", timeout=20).json()
        if isinstance(pub, dict):
            pub = pub.get("articles") or pub.get("items") or []
        slugs = [x.get("slug") for x in pub]
        assert slug not in slugs, "draft (unpublished) leaked into public list"

        # PATCH title
        r = requests.patch(
            f"{API}/admin/blogs/articles/{article_id}",
            json={"title_en": "TEST iter331 article UPDATED"},
            headers=H(admin_token),
            timeout=30,
        )
        assert r.status_code in (200, 204), f"patch failed: {r.status_code} {r.text}"

        # PUBLISH
        r = requests.post(f"{API}/admin/blogs/articles/{article_id}/publish", headers=H(admin_token), timeout=30)
        assert r.status_code in (200, 204), f"publish failed: {r.status_code} {r.text}"

        # Now appears in public list
        time.sleep(0.5)
        pub = requests.get(f"{API}/blogs/articles", timeout=20).json()
        if isinstance(pub, dict):
            pub = pub.get("articles") or pub.get("items") or []
        slugs = [x.get("slug") for x in pub]
        assert slug in slugs, "published article missing from public list"

        # UNPUBLISH
        r = requests.post(f"{API}/admin/blogs/articles/{article_id}/unpublish", headers=H(admin_token), timeout=30)
        assert r.status_code in (200, 204), r.text

        pub = requests.get(f"{API}/blogs/articles", timeout=20).json()
        if isinstance(pub, dict):
            pub = pub.get("articles") or pub.get("items") or []
        slugs = [x.get("slug") for x in pub]
        assert slug not in slugs, "unpublished article still in public list"

        # DELETE
        r = requests.delete(f"{API}/admin/blogs/articles/{article_id}", headers=H(admin_token), timeout=30)
        assert r.status_code in (200, 204), r.text

        # 404 by slug after delete
        r = requests.get(f"{API}/blogs/articles/{slug}", timeout=20)
        assert r.status_code == 404, f"expected 404 after delete, got {r.status_code}"

    def test_non_admin_rejected(self, buyer_token):
        r = requests.post(
            f"{API}/admin/blogs/articles",
            json={"slug": "nope-iter331", "title_en": "nope", "title_fr": "nope"},
            headers=H(buyer_token),
            timeout=30,
        )
        assert r.status_code in (401, 403), f"non-admin should be rejected, got {r.status_code}: {r.text}"


# ---------- Cover Upload ----------

class TestCoverUpload:
    def test_cover_upload(self, admin_token):
        # tiny 1x1 PNG bytes
        png_bytes = bytes.fromhex(
            "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4890000000A49444154789C6300010000000500010D0A2DB40000000049454E44AE426082"
        )
        files = {"file": ("cover.png", io.BytesIO(png_bytes), "image/png")}
        headers = {"Authorization": f"Bearer {admin_token}"}
        r = requests.post(f"{API}/admin/blogs/articles/cover-upload", files=files, headers=headers, timeout=60)
        # S3 missing creds -> 500 acceptable per spec
        assert r.status_code in (200, 201, 500), f"unexpected status {r.status_code}: {r.text[:300]}"
        if r.status_code in (200, 201):
            body = r.json()
            assert "cover_url" in body or "url" in body, f"missing cover_url: {body}"


# ---------- Contractor Aid Info ----------

class TestContractorAidInfo:
    def test_info_admin(self, admin_token):
        r = requests.get(f"{API}/contractor/aid/info", headers=H(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        sections = data.get("sections") or data.get("workflows") or []
        assert len(sections) == 6, f"expected 6 sections, got {len(sections)}"
        assert data.get("support_email")
        assert data.get("model")

    def test_info_non_contractor_rejected(self, buyer_token):
        r = requests.get(f"{API}/contractor/aid/info", headers=H(buyer_token), timeout=30)
        assert r.status_code in (401, 403), f"expected 403 for non-contractor non-admin, got {r.status_code}"


# ---------- Contractor Aid Chat (Gemini) ----------

class TestContractorAidChat:
    def test_chat_max_rate_question(self, admin_token):
        payload = {"message": "What is the maximum effective commission rate?"}
        r = requests.post(f"{API}/contractor/aid/chat", json=payload, headers=H(admin_token), timeout=90)
        assert r.status_code == 200, f"chat failed: {r.status_code} {r.text[:400]}"
        data = r.json()
        reply = data.get("reply") or ""
        sid = data.get("session_id")
        model = data.get("model")
        assert reply, "empty reply"
        assert sid, "missing session_id"
        # Model identifier should mention gemini-3-flash
        assert model and "gemini-3-flash" in str(model).lower(), f"unexpected model: {model}"
        assert ("20%" in reply) or ("20.0%" in reply) or ("20 %" in reply), f"reply missing 20%: {reply[:400]}"
