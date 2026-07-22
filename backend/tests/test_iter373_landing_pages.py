"""
iter373 — Admin Landing Page Builder backend tests.

Covers every acceptance criterion in the spec:
  • Slug validation (shape + reserved + collision)
  • Admin authorization gate
  • Full CRUD lifecycle (create, read, update, delete, publish/unpublish, duplicate)
  • Duplicate creates a "-copy" slug, incremented when taken
  • Public /lp/{slug} returns 404 for draft/archived and 200 for published
  • ?lang=en|fr override + Accept-Language fall-back
  • view_count + view_buckets increment on each hit
  • HTML sanitisation strips <script> + event handlers
  • Full HTML render includes SEO title, description, canonical, OG tags,
    and BidVex header/footer when flagged
"""
import asyncio
import os

import httpx
import pytest
import bcrypt
import uuid
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
INTERNAL_BASE = "http://localhost:8001"
API = f"{INTERNAL_BASE}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

ADMIN_EMAIL = "iter373_lp_admin@bidvex.com"
ADMIN_PASSWORD = "Iter373LP!"
USER_EMAIL = "iter373_lp_user@bidvex.com"
USER_PASSWORD = "Iter373LPUser!"


# ─── Fixtures ───────────────────────────────────────────────────────────


def _get_token(email: str, password: str) -> str:
    """Log a seeded user in and return their JWT."""
    async def go():
        async with httpx.AsyncClient(base_url=API, timeout=30) as x:
            r = await x.post("/auth/login", json={"email": email, "password": password})
            r.raise_for_status()
            return r.json()["access_token"]
    return asyncio.run(go())


async def _seed_users():
    """Idempotently seed one admin + one regular user for these tests."""
    c = AsyncIOMotorClient(MONGO_URL)
    db = c[DB_NAME]
    for email, pw, role in (
        (ADMIN_EMAIL, ADMIN_PASSWORD, "admin"),
        (USER_EMAIL, USER_PASSWORD, "user"),
    ):
        h = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
        await db.users.update_one(
            {"email": email},
            {"$set": {
                "id": f"iter373-{role}",
                "email": email,
                "password_hash": h,
                "role": role,
                "name": f"iter373 {role}",
                "phone_verified": True,
                "email_verified": True,
                "id_verified": True,
                "has_payment_method": True,
                "account_type": "individual",
                "subscription_tier": "premium" if role == "admin" else "standard",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
    c.close()


async def _cleanup():
    c = AsyncIOMotorClient(MONGO_URL)
    db = c[DB_NAME]
    await db.landing_pages.delete_many({"slug": {"$regex": "^iter373-"}})
    await db.landing_page_audit_log.delete_many({})
    await db.landing_page_views.delete_many({})
    c.close()


@pytest.fixture(scope="module", autouse=True)
def _prepare():
    asyncio.run(_seed_users())
    asyncio.run(_cleanup())
    yield
    asyncio.run(_cleanup())


@pytest.fixture(scope="module")
def admin_token() -> str:
    return _get_token(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def user_token() -> str:
    return _get_token(USER_EMAIL, USER_PASSWORD)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─── Admin authorization ────────────────────────────────────────────────


def test_admin_endpoints_require_admin(user_token, admin_token):
    async def go():
        async with httpx.AsyncClient(base_url=API, timeout=30) as x:
            # Anonymous → 401 (no auth header).
            assert (await x.get("/admin/landing-pages")).status_code == 401
            # Regular user → 403.
            r = await x.get("/admin/landing-pages", headers=_auth(user_token))
            assert r.status_code == 403, r.text
            # Admin → 200.
            r = await x.get("/admin/landing-pages", headers=_auth(admin_token))
            assert r.status_code == 200
            j = r.json()
            assert "items" in j and "total" in j
    asyncio.run(go())


# ─── Slug validation ────────────────────────────────────────────────────


def test_slug_validation_rejects_bad_shapes(admin_token):
    bads = [
        "UPPER-case", "with_underscore", "double--hyphen",
        "-leading", "trailing-", "space in", "sym!bol", "à-accented",
        "a", "x" * 100,   # too short / too long
        "api", "admin", "sitemap.xml",   # reserved
    ]
    async def go():
        async with httpx.AsyncClient(base_url=API, timeout=30) as x:
            for slug in bads:
                r = await x.post("/admin/landing-pages", headers=_auth(admin_token), json={
                    "slug": slug, "title_en": "T", "html_en": "<p>x</p>",
                })
                assert r.status_code in (400, 422, 409), (slug, r.status_code, r.text)
    asyncio.run(go())


def test_slug_validation_accepts_good_shapes(admin_token):
    goods = ["iter373-fresh", "iter373-with-2-numbers-9", "iter373-abc"]
    async def go():
        async with httpx.AsyncClient(base_url=API, timeout=30) as x:
            for slug in goods:
                # Ensure not present first.
                r = await x.post("/admin/landing-pages", headers=_auth(admin_token), json={
                    "slug": slug, "title_en": "OK", "html_en": "<p>ok</p>",
                })
                assert r.status_code == 200, (slug, r.status_code, r.text)
    asyncio.run(go())


def test_duplicate_slug_returns_409(admin_token):
    slug = "iter373-dup"
    async def go():
        async with httpx.AsyncClient(base_url=API, timeout=30) as x:
            r1 = await x.post("/admin/landing-pages", headers=_auth(admin_token), json={
                "slug": slug, "title_en": "A", "html_en": "<p>a</p>",
            })
            assert r1.status_code == 200
            r2 = await x.post("/admin/landing-pages", headers=_auth(admin_token), json={
                "slug": slug, "title_en": "B", "html_en": "<p>b</p>",
            })
            assert r2.status_code == 409, r2.text
            assert "duplicate_slug" in r2.text
    asyncio.run(go())


# ─── Full CRUD lifecycle ────────────────────────────────────────────────


def _create(slug: str, admin_token: str, extra: dict | None = None) -> dict:
    async def go():
        async with httpx.AsyncClient(base_url=API, timeout=30) as x:
            body = {"slug": slug, "title_en": f"Title {slug}",
                    "html_en": "<p>hi</p>", "html_fr": "<p>bonjour</p>"}
            if extra:
                body.update(extra)
            r = await x.post("/admin/landing-pages", headers=_auth(admin_token), json=body)
            assert r.status_code == 200, r.text
            return r.json()
    return asyncio.run(go())


def test_full_crud_lifecycle(admin_token):
    page = _create("iter373-crud", admin_token)
    pid = page["id"]
    assert page["status"] == "draft"
    assert page["view_count"] == 0
    assert page["analytics"]["total_views"] == 0

    async def go():
        async with httpx.AsyncClient(base_url=API, timeout=30) as x:
            # GET
            r = await x.get(f"/admin/landing-pages/{pid}", headers=_auth(admin_token))
            assert r.status_code == 200
            assert r.json()["slug"] == "iter373-crud"
            # PATCH
            r = await x.patch(f"/admin/landing-pages/{pid}", headers=_auth(admin_token), json={
                "title_en": "Updated", "meta_description_en": "meta v2",
            })
            assert r.status_code == 200
            j = r.json()
            assert j["title_en"] == "Updated"
            assert j["meta_description_en"] == "meta v2"
            # Publish
            r = await x.post(f"/admin/landing-pages/{pid}/publish", headers=_auth(admin_token))
            assert r.status_code == 200
            assert r.json()["status"] == "published"
            assert r.json()["published_at"] is not None
            # Unpublish
            r = await x.post(f"/admin/landing-pages/{pid}/unpublish", headers=_auth(admin_token))
            assert r.status_code == 200
            assert r.json()["status"] == "draft"
            # Publish again for the public tests below
            await x.post(f"/admin/landing-pages/{pid}/publish", headers=_auth(admin_token))
            # DELETE → archived
            r = await x.delete(f"/admin/landing-pages/{pid}", headers=_auth(admin_token))
            assert r.status_code == 200
            r = await x.get(f"/admin/landing-pages/{pid}", headers=_auth(admin_token))
            assert r.json()["status"] == "archived"
    asyncio.run(go())


def test_publish_rejects_incomplete_page(admin_token):
    page = _create("iter373-empty-body", admin_token, {"html_en": "", "html_fr": ""})
    async def go():
        async with httpx.AsyncClient(base_url=API, timeout=30) as x:
            r = await x.post(f"/admin/landing-pages/{page['id']}/publish",
                             headers=_auth(admin_token))
            assert r.status_code == 422
            assert "incomplete_page" in r.text
    asyncio.run(go())


def test_duplicate_creates_copy_slug(admin_token):
    src = _create("iter373-source", admin_token)
    async def go():
        async with httpx.AsyncClient(base_url=API, timeout=30) as x:
            r = await x.post(f"/admin/landing-pages/{src['id']}/duplicate",
                             headers=_auth(admin_token))
            assert r.status_code == 200
            dup1 = r.json()
            assert dup1["slug"] == "iter373-source-copy"
            assert dup1["status"] == "draft"
            assert dup1["view_count"] == 0
            assert dup1["duplicated_from"] == src["id"]
            # Duplicate again → "-copy-2"
            r = await x.post(f"/admin/landing-pages/{src['id']}/duplicate",
                             headers=_auth(admin_token))
            assert r.status_code == 200
            assert r.json()["slug"] == "iter373-source-copy-2"
    asyncio.run(go())


# ─── Public rendering ───────────────────────────────────────────────────


def test_public_only_serves_published_pages(admin_token):
    page = _create("iter373-draft", admin_token)
    async def go():
        async with httpx.AsyncClient(base_url=INTERNAL_BASE, timeout=30) as x:
            # Draft → 404
            r = await x.get(f"/api/lp/{page['slug']}")
            assert r.status_code == 404
            r = await x.get(f"/api/lp/{page['slug']}/render")
            assert r.status_code == 404
        # Publish → 200
        async with httpx.AsyncClient(base_url=API, timeout=30) as x:
            r = await x.post(f"/admin/landing-pages/{page['id']}/publish",
                             headers=_auth(admin_token))
            assert r.status_code == 200
        async with httpx.AsyncClient(base_url=INTERNAL_BASE, timeout=30) as x:
            r = await x.get(f"/api/lp/{page['slug']}")
            assert r.status_code == 200
            assert r.json()["slug"] == page["slug"]
            # Archive → 404 again
        async with httpx.AsyncClient(base_url=API, timeout=30) as x:
            await x.delete(f"/admin/landing-pages/{page['id']}", headers=_auth(admin_token))
        async with httpx.AsyncClient(base_url=INTERNAL_BASE, timeout=30) as x:
            r = await x.get(f"/api/lp/{page['slug']}")
            assert r.status_code == 404
    asyncio.run(go())


def test_language_override_and_accept_language(admin_token):
    page = _create("iter373-i18n", admin_token, {
        "title_en": "Hello", "title_fr": "Bonjour",
        "html_en": "<p>en body</p>", "html_fr": "<p>fr body</p>",
    })
    async def go():
        async with httpx.AsyncClient(base_url=API, timeout=30) as x:
            await x.post(f"/admin/landing-pages/{page['id']}/publish", headers=_auth(admin_token))
        async with httpx.AsyncClient(base_url=INTERNAL_BASE, timeout=30) as x:
            # ?lang=fr
            r = await x.get(f"/api/lp/{page['slug']}?lang=fr")
            assert r.json()["locale"] == "fr"
            assert r.json()["title"] == "Bonjour"
            # ?lang=en
            r = await x.get(f"/api/lp/{page['slug']}?lang=en")
            assert r.json()["locale"] == "en"
            # Accept-Language header
            r = await x.get(f"/api/lp/{page['slug']}",
                            headers={"Accept-Language": "fr-CA,fr;q=0.9,en;q=0.5"})
            assert r.json()["locale"] == "fr"
            r = await x.get(f"/api/lp/{page['slug']}",
                            headers={"Accept-Language": "en-US,en;q=0.9"})
            assert r.json()["locale"] == "en"
    asyncio.run(go())


def test_view_count_increments(admin_token):
    page = _create("iter373-views", admin_token)
    async def go():
        async with httpx.AsyncClient(base_url=API, timeout=30) as x:
            await x.post(f"/admin/landing-pages/{page['id']}/publish", headers=_auth(admin_token))
        async with httpx.AsyncClient(base_url=INTERNAL_BASE, timeout=30) as x:
            # Hit the public JSON endpoint three times.
            for _ in range(3):
                r = await x.get(f"/api/lp/{page['slug']}",
                                headers={"Referer": "https://google.com/search?q=x"})
                assert r.status_code == 200
        # Read view_count off the admin detail.
        async with httpx.AsyncClient(base_url=API, timeout=30) as x:
            r = await x.get(f"/admin/landing-pages/{page['id']}", headers=_auth(admin_token))
            j = r.json()
            assert j["view_count"] >= 3
            assert j["analytics"]["total_views"] >= 3
            assert j["analytics"]["views_7d"] >= 3
            assert j["analytics"]["views_30d"] >= 3
            # Google origin should be in the top referrers list.
            origins = [r["origin"] for r in j["analytics"]["top_referrers"]]
            assert any("google.com" in o for o in origins)
    asyncio.run(go())


def test_full_html_render_includes_seo_and_body(admin_token):
    page = _create("iter373-render", admin_token, {
        "title_en": "SEO Title",
        "meta_description_en": "SEO description example",
        "html_en": "<h1 data-testid='hero'>Hello</h1>",
        "css": ".hero{color:red}",
        "js": "console.log('boot');",
        "og_image_url": "https://cdn.example.com/og.png",
        "show_bidvex_header": True,
        "show_bidvex_footer": True,
    })
    async def go():
        async with httpx.AsyncClient(base_url=API, timeout=30) as x:
            await x.post(f"/admin/landing-pages/{page['id']}/publish", headers=_auth(admin_token))
        async with httpx.AsyncClient(base_url=INTERNAL_BASE, timeout=30) as x:
            r = await x.get(f"/api/lp/{page['slug']}/render")
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/html")
            html = r.text
            # SEO
            assert "<title" in html and "SEO Title" in html
            assert 'name="description"' in html and "SEO description example" in html
            assert 'rel="canonical"' in html
            assert 'property="og:title"' in html
            assert 'property="og:description"' in html
            assert 'og:image' in html and 'cdn.example.com/og.png' in html
            # Custom body + assets
            assert 'data-testid=\'hero\'' in html or 'data-testid="hero"' in html
            assert ".hero{color:red}" in html
            assert "console.log('boot');" in html
            # Header + footer flags
            assert 'bidvex-lp-header' in html
            assert 'bidvex-lp-footer' in html
    asyncio.run(go())


def test_bidvex_header_footer_toggle(admin_token):
    page = _create("iter373-chrome-off", admin_token, {
        "show_bidvex_header": False, "show_bidvex_footer": False,
    })
    async def go():
        async with httpx.AsyncClient(base_url=API, timeout=30) as x:
            await x.post(f"/admin/landing-pages/{page['id']}/publish", headers=_auth(admin_token))
        async with httpx.AsyncClient(base_url=INTERNAL_BASE, timeout=30) as x:
            r = await x.get(f"/api/lp/{page['slug']}/render")
            html = r.text
            assert "bidvex-lp-header" not in html
            assert "bidvex-lp-footer" not in html
    asyncio.run(go())


# ─── Sanitisation ───────────────────────────────────────────────────────


def test_html_sanitisation_strips_script_and_event_handlers(admin_token):
    dangerous_html = (
        "<p onclick='alert(1)'>hi</p>"
        "<script>alert('xss')</script>"
        "<a href='javascript:alert(1)'>bad</a>"
        "<img src=x onerror='alert(1)'>"
    )
    page = _create("iter373-xss", admin_token, {"html_en": dangerous_html})
    async def go():
        async with httpx.AsyncClient(base_url=API, timeout=30) as x:
            await x.post(f"/admin/landing-pages/{page['id']}/publish", headers=_auth(admin_token))
        async with httpx.AsyncClient(base_url=INTERNAL_BASE, timeout=30) as x:
            r = await x.get(f"/api/lp/{page['slug']}/render")
            html = r.text
            body_start = html.find('data-testid="lp-body"')
            body_slice = html[body_start:body_start + 800]
            # <script> stripped from body region.
            assert "<script>alert" not in body_slice
            # Inline onclick / onerror stripped.
            assert "onclick=" not in body_slice
            assert "onerror=" not in body_slice
            # javascript: URL replaced by bleach.
            assert "javascript:alert" not in body_slice
    asyncio.run(go())


# ─── Audit log ──────────────────────────────────────────────────────────


def test_audit_log_records_updates(admin_token):
    page = _create("iter373-audit", admin_token)
    async def go():
        async with httpx.AsyncClient(base_url=API, timeout=30) as x:
            await x.patch(f"/admin/landing-pages/{page['id']}", headers=_auth(admin_token), json={
                "html_en": "<p>Version 2</p>",
            })
            await x.post(f"/admin/landing-pages/{page['id']}/publish", headers=_auth(admin_token))
            r = await x.get(f"/admin/landing-pages/{page['id']}/audit-log",
                            headers=_auth(admin_token))
            assert r.status_code == 200
            actions = [e["action"] for e in r.json()["entries"]]
            # Should carry at least create/update/publish.
            assert "create" in actions and "update" in actions and "publish" in actions
    asyncio.run(go())
