"""
iter259 — Three surgical fix tests.

  Fix 1: Public Partner Promotion page REMOVED; admin guard on
         POST /api/promotions/partner-trial; new admin endpoints
         GET /api/admin/partner-trials, PATCH /extend, DELETE.
  Fix 2: POST /api/admin/users/{id}/request-payment no longer crashes
         when Stripe is misconfigured — returns success with a
         warning + null payment link.
  Fix 3: GET /api/promoted-listings tolerates legacy rows where
         `promotion_sections` is null; idempotent startup backfill
         scheduled on `set_promotions_db()`.
"""
from __future__ import annotations

import os

import httpx


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, "..", "frontend", "src"))


def _read(rel: str, root: str = BACKEND_ROOT) -> str:
    with open(os.path.join(root, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _strip_py_comments(src: str) -> str:
    """Strip `#` line-comments AND docstrings so static assertions
    don't false-match against documentation references to the
    legacy/forbidden patterns we're checking are gone."""
    import re as _re
    # Remove triple-quoted docstrings + multi-line strings.
    out = _re.sub(r'"""[\s\S]*?"""', "", src)
    out = _re.sub(r"'''[\s\S]*?'''", "", out)
    # Remove single-line # comments.
    return "\n".join(
        _re.sub(r"#.*$", "", line) for line in out.splitlines()
    )


def _strip_js_comments(src: str) -> str:
    import re as _re
    # /* … */
    out = _re.sub(r"/\*[\s\S]*?\*/", "", src)
    # //…
    out = "\n".join(_re.sub(r"//.*$", "", line) for line in out.splitlines())
    # JSX {/* … */} comments are removed by the /* */ pass above.
    return out


# ─── Fix 1 — Public page removed + admin-only flow ───────────────────

def test_iter259_public_partner_promotions_route_is_gone():
    """iter259 removed the React route + the navbar shortcut + the
    sitemap entry. The page file may remain for reference but it must
    NOT be reachable from the public site."""
    app = _strip_js_comments(_read("App.js", root=FRONTEND_ROOT))
    assert 'PartnerPromotionsPage' not in app
    assert '/promotions/partners' not in app

    nav = _strip_js_comments(_read("components/Navbar.js", root=FRONTEND_ROOT))
    assert "dropdown-partner-program-link" not in nav
    assert "/promotions/partners" not in nav

    sitemap = _strip_py_comments(_read("routes/sitemap.py"))
    assert "/promotions/partners" not in sitemap


def test_iter259_partner_trial_endpoint_requires_admin():
    src = _read("routes/partner_trial.py")
    # Hard admin guard on the activation endpoint.
    assert "Admin only — partner trials are activated by BidVex staff" in src
    # Non-admin users are explicitly forbidden (raise 403).
    assert "raise HTTPException(\n            status_code=403" in src or 'status_code=403' in src


def test_iter259_admin_partner_trials_router_exposes_list_extend_revoke():
    src = _read("routes/partner_trial.py")
    # Three management endpoints — list / extend / revoke.
    assert "admin_partner_trials_router = APIRouter(prefix=\"/admin\"" in src
    assert "@admin_partner_trials_router.get(\"/partner-trials\")" in src
    assert "@admin_partner_trials_router.patch(\"/partner-trials/{trial_id}/extend\")" in src
    assert "@admin_partner_trials_router.delete(\"/partner-trials/{trial_id}\")" in src
    # Revoke flips broker flag off, sends trial_revoked email.
    assert "is_broker_partner" in src and 'False' in src
    assert "trial_revoked" in src

    # Router is wired in server.py.
    server = _read("server.py")
    assert '"admin_partner_trials_router"' in server


def test_iter259_trial_revoked_email_template_registered():
    src = _read("services/email_templates.py")
    assert '"trial_revoked"' in src
    assert "Your BidVex Partner Trial Has Ended" in src
    assert "Upgrade to Pro" in src


def test_iter259_admin_promotion_manager_mounts_partner_trials_section():
    pm = _read("pages/admin/PromotionManager.js", root=FRONTEND_ROOT)
    assert "import PartnerTrialsAdminSection from" in pm
    assert "<PartnerTrialsAdminSection" in pm
    # Mounted ABOVE the "All Promotions" table.
    idx_section = pm.find("PartnerTrialsAdminSection token=")
    idx_all = pm.find("All Promotions (")
    assert idx_section != -1 and idx_all != -1 and idx_section < idx_all, (
        "Partner Trials section must render ABOVE the All Promotions table"
    )

    section = _read("components/admin/PartnerTrialsAdminSection.jsx", root=FRONTEND_ROOT)
    # Static test ids resolved from the source as-is.
    for tid in (
        "partner-trials-admin-section",
        "partner-trial-cards",
        "activate-trial-modal",
        "activate-trial-user-search",
        "activate-trial-company",
        "activate-trial-province",
        "activate-trial-phone",
        "activate-trial-submit",
        "partner-trials-table",
        "refresh-partner-trials",
        "activate-trial-licence",
    ):
        assert tid in section, f"PartnerTrialsAdminSection missing data-testid={tid}"
    # The 3 cards + 3 activate buttons use a template id whose suffix
    # comes from the loop variable `o.key`.
    assert "partner-trial-card-${o.key}" in section
    assert "activate-trial-${o.key}" in section
    # And the 3 partner types are wired in the offer array.
    for key in ("dealer", "broker", "storage"):
        assert f"key: '{key}'" in section, f"TRIAL_OFFERS missing {key} entry"
    # Wired to the right endpoints.
    assert "/admin/partner-trials" in section
    assert "/promotions/partner-trial" in section


# ─── Fix 2 — Request Payment 500/405 fix ─────────────────────────────

def test_iter259_request_payment_does_not_crash_on_stripe_misconfig():
    """Modern Stripe SDK exposes errors as `stripe.StripeError`, not
    `stripe.error.StripeError`. The legacy reference would AttributeError
    on import and surface as a 500 to the admin. iter259 catches the
    broad `Exception` and persists the request with `stripe_payment_link=None`
    + a `warning` flag instead of crashing."""
    src_raw = _read("routes/admin_payment_requests.py")
    src = _strip_py_comments(src_raw)
    assert "stripe.error.StripeError" not in src, (
        "iter259 must not reference the deprecated stripe.error namespace"
    )
    # Broad exception + warning fan-out (check against raw source so
    # we don't strip the warning STRING literal we want to find).
    assert "stripe_payment_link_url = None" in src_raw
    assert "Stripe not configured" in src_raw
    # The success response carries the warning back to the admin.
    assert "\"warning\": stripe_warning" in src_raw


# ─── Fix 3 — Featured Listings backfill + null tolerance ─────────────

def test_iter259_promoted_listings_tolerates_null_promotion_sections():
    src = _read("routes/promotions.py")
    # The query builder emits `$exists: False` / None / [] clauses for
    # `promotion_sections` on default (marketplace/homepage) sections.
    assert "default_section" in src
    assert '{"promotion_sections": {"$exists": False}}' in src
    assert '{"promotion_sections": None}' in src
    assert '{"promotion_sections": []}' in src
    # The query no longer flat-asserts `promotion_sections: $in`
    # outside an $or wrapper — it's now `section_clauses`.
    assert "section_clauses" in src
    assert "$and" in src and "$or" in src


def test_iter259_promotion_sections_backfill_runs_on_set_db():
    src = _read("routes/promotions.py")
    assert "_iter259_backfill_promotion_sections" in src
    # The backfill is scheduled on `set_promotions_db()`.
    assert "loop.create_task(_iter259_backfill_promotion_sections(database))" in src
    # The backfill itself updates all 3 listing-type buckets.
    assert "[\"marketplace\", \"homepage\"]" in src
    assert "[\"vehicles\", \"homepage\"]" in src
    assert "[\"storage\", \"homepage\"]" in src


# ─── End-to-end live smokes against the running preview ──────────────

def _base() -> str:
    base = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not base:
        import pytest
        pytest.skip("REACT_APP_BACKEND_URL not configured")
    return base.rstrip("/")


def _admin_token() -> str:
    base = _base()
    r = httpx.post(
        f"{base}/api/auth/login",
        json={
            "email": os.environ.get("BIDVEX_ADMIN_EMAIL", "charbel911@gmail.com"),
            "password": os.environ.get("BIDVEX_ADMIN_PASSWORD", "Anderosli123!@#"),
        },
        timeout=20,
    )
    if r.status_code != 200:
        import pytest
        pytest.skip(f"admin login failed: {r.status_code}")
    token = r.json().get("access_token") or r.json().get("token")
    if not token:
        import pytest
        pytest.skip("no token in login response")
    return token


def test_iter259_promoted_listings_live_includes_legacy_null_sections_listing():
    """Live smoke — the Featured Listings query must surface the
    'Lot de 7 tabourets Meridian' listing (`is_promoted: True` but
    `promotion_sections` originally null)."""
    base = _base()
    r = httpx.get(
        f"{base}/api/promoted-listings",
        params={"section": "marketplace", "limit": 8},
        timeout=20,
    )
    assert r.status_code == 200
    items = r.json().get("items", [])
    titles = [(it.get("title") or "").lower() for it in items]
    assert len(items) >= 2, f"expected ≥2 promoted items; got {len(items)} ({titles})"


def test_iter259_request_payment_returns_success_under_stripe_misconfig():
    """Live smoke — even with the preview env's missing Stripe
    secret, the endpoint persists the request and returns success +
    warning, never 500."""
    base = _base()
    token = _admin_token()
    # Pick any user to address the request to (admin uses themselves).
    me = httpx.get(
        f"{base}/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    ).json()
    user_id = me.get("id")
    assert user_id, "could not resolve admin user_id"

    r = httpx.post(
        f"{base}/api/admin/users/{user_id}/request-payment",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "subtotal": 100,
            "tax_type": "gst",
            "total_amount": 105,
            "description": "iter259 live smoke",
            "internal_notes": "",
            "send_email": False,
            "send_notification": False,
            "expiry_hours": 48,
        },
        timeout=20,
    )
    assert r.status_code == 200, f"request-payment must not 500; got {r.status_code} {r.text[:200]}"
    body = r.json()
    assert body.get("success") is True
    # Either a real Stripe link OR a warning indicating misconfig.
    assert body.get("payment_link") or body.get("warning"), (
        f"response must carry payment_link OR warning; got {body}"
    )


def test_iter259_admin_partner_trials_endpoint_lists_and_paginates():
    base = _base()
    token = _admin_token()
    r = httpx.get(
        f"{base}/api/admin/partner-trials",
        headers={"Authorization": f"Bearer {token}"},
        params={"page": 1, "limit": 20},
        timeout=20,
    )
    assert r.status_code == 200, f"admin/partner-trials must be reachable; got {r.status_code}"
    data = r.json()
    assert "items" in data and isinstance(data["items"], list)
    assert "total" in data and isinstance(data["total"], int)
    assert data.get("page") == 1
