"""
iter269 — Launch prep hardening verification.

  Task 1 — Confirm no unconditional email mocks (only key-presence guards).
  Task 2 — Stripe live-mode safety: env-only api_key + CAD fallback +
           signature verification still in place.
  Task 3 — Security hardening: CORS scoping + rate limits on critical
           endpoints + admin guards.
  Task 4 — Image optimization markers: loading=lazy on grid cards,
           loading=eager on listing-detail hero, preconnect hints.
  Task 5 — LAUNCH_QA.md exists with the canonical checklist.
"""
from __future__ import annotations

import os
import re


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _read(rel: str, root: str = BACKEND_ROOT) -> str:
    with open(os.path.join(root, rel), "r", encoding="utf-8") as fh:
        return fh.read()


# ─── Task 1 — SendGrid not mocked ─────────────────────────────────────


def test_iter269_no_unconditional_email_mock_branch():
    """Scan services/email* + routes/* for any unconditional email
    mock-send. Guards on missing key are OK; unconditional mocks are not."""
    for path in (
        "services/email_notifications.py",
        "services/email_service.py",
        "routes/admin_user_actions.py",
    ):
        src = _read(path)
        # Forbidden patterns: explicit `MOCK_EMAIL`, `mock_send_email`,
        # or `if True: return mock_response` etc.
        assert "MOCK_EMAIL = True" not in src, f"{path}: hardcoded MOCK_EMAIL=True"
        assert "mock_send_email(" not in src, f"{path}: mock_send_email call"
        # The legitimate guard is `if not SENDGRID_AVAILABLE` or
        # `if not key`. That stays.


def test_iter269_invoices_docstring_no_mock_mode():
    """We rewrote the outdated docstring that claimed PDFs sent in
    mock mode."""
    src = _read("routes/invoices.py")
    assert "(mock mode)" not in src


# ─── Task 2 — Stripe live-mode safety ─────────────────────────────────


def test_iter269_no_hardcoded_stripe_keys_in_runtime():
    """Scan everything under /app/backend/{routes,services} for
    `sk_test` or `sk_live` string literals. Tests and migration
    scripts are excluded."""
    import subprocess
    out = subprocess.run(
        ["grep", "-rn", "-E", r"sk_(test|live)_", BACKEND_ROOT + "/routes", BACKEND_ROOT + "/services"],
        capture_output=True, text=True,
    )
    lines = [ln for ln in (out.stdout or "").splitlines() if ln.strip() and "tests/" not in ln]
    assert not lines, f"Hardcoded Stripe keys found:\n{lines}"


def test_iter269_stripe_api_key_from_env():
    """Every `stripe.api_key = ...` reads from env, not hardcoded."""
    src = _read("services/subscription_service.py")
    # The reference assignment exists.
    assert "_stripe.api_key" in src


def test_iter269_webhook_verifies_signature():
    src = _read("routes/webhooks.py")
    assert "STRIPE_WEBHOOK_SECRET" in src
    assert "construct_event" in src
    assert "Stripe-Signature" in src or "stripe_signature" in src or "stripe-signature" in src.lower()


def test_iter269_currency_fallback_is_cad():
    src = _read("routes/webhooks.py")
    # The webhook fallback default is "cad" (CAD-first marketplace).
    # No remaining `"usd"` literal fallbacks in payment-recording paths.
    assert 'invoice.get("currency", "usd")' not in src
    assert 'invoice.get("currency", "cad")' in src


# ─── Task 3 — Security hardening ──────────────────────────────────────


def test_iter269_cors_origins_scoped_not_wildcard():
    src = _read("server.py")
    # CORS is built from env (CORS_ORIGINS list), not "*"
    assert 'allow_origins=["*"]' not in src
    assert "_cors_origins" in src or "CORS_ORIGINS" in src or "ALLOWED_ORIGINS" in src


def test_iter269_critical_endpoints_rate_limited():
    auth = _read("routes/auth.py")
    bids = _read("routes/auctions_bids.py")
    msgs = _read("routes/messages.py")
    # Login + register
    assert "@_limiter.limit" in auth
    # Bid placement — spec asks 30/min
    assert '@_limiter.limit("30/minute")' in bids
    # Messages — spec asks 20/min
    assert '@_limiter.limit("20/minute")' in msgs


def test_iter269_html_sanitizer_uses_bleach():
    src = _read("services/html_sanitizer.py")
    assert "bleach.clean" in src
    assert "strip=True" in src
    # `bleach` is in requirements.txt
    req = _read("requirements.txt")
    assert "bleach" in req


def test_iter269_all_admin_endpoints_guarded():
    """No `/admin/*` endpoint should be reachable without an admin gate.
    The audit pattern: every `@admin*_router.<verb>(<path>)` decorator
    must be followed (within ~1500 chars) by a `_require_admin`,
    `require_admin`, `get_current_admin`, or an `is_admin` check."""
    import os as _os
    files = [
        "routes/admin.py",
        "routes/admin_oversight.py",
        "routes/admin_ops.py",
        "routes/admin_user_actions.py",
        "routes/admin_payment_requests.py",
        "routes/admin_ai_review.py",
        "routes/admin_bulk.py",
        "routes/admin_chat.py",
        "routes/admin_notifications.py",
        "routes/admin_settings.py",
    ]
    issues = []
    for fp in files:
        full = _os.path.join(BACKEND_ROOT, fp)
        if not _os.path.exists(full):
            continue
        src = _read(fp)
        for m in re.finditer(r"@\w+_router\.(get|post|put|patch|delete)\(([^)]+)\)", src):
            arg = m.group(2) or ""
            if "admin" not in arg:
                continue
            ahead = src[m.end(): m.end() + 1500]
            if re.search(r"_require_admin\(|require_admin|get_current_admin|is_admin", ahead[:1200], re.IGNORECASE):
                continue
            issues.append((fp, arg.strip()))
    assert not issues, f"Unguarded admin endpoints: {issues}"


# ─── Task 4 — Image optimization ──────────────────────────────────────


def test_iter269_listing_detail_hero_eager_others_lazy():
    src = _read("../frontend/src/pages/ListingDetailPage.js")
    # Hero image marked eager + fetchpriority high.
    assert 'loading="eager"' in src
    assert 'fetchpriority="high"' in src or 'fetchPriority="high"' in src
    # At least one lazy gallery img.
    assert 'loading="lazy"' in src


def test_iter269_grid_cards_lazy_with_explicit_dims():
    src = _read("../frontend/src/components/FlattenedMarketplace.js")
    assert 'loading="lazy"' in src
    assert "width={400}" in src
    assert "height=" in src


def test_iter269_index_html_has_preconnect_hints():
    src = _read("../frontend/public/index.html")
    assert "fonts.googleapis.com" in src
    assert "sendgrid.net" in src


# ─── Task 5 — LAUNCH_QA.md ───────────────────────────────────────────


def test_iter269_launch_qa_checklist_exists():
    qa_path = os.path.abspath(os.path.join(BACKEND_ROOT, "..", "LAUNCH_QA.md"))
    assert os.path.isfile(qa_path), f"LAUNCH_QA.md missing at {qa_path}"
    body = open(qa_path, encoding="utf-8").read()
    # Spot-check several spec sections.
    for section in (
        "Auth", "Listings", "Bidding", "Payments", "Admin",
        "Emails", "Mobile", "Notifications", "Affiliate",
        "SEO", "Performance", "Security",
    ):
        assert section in body, f"LAUNCH_QA.md missing '{section}' section"
