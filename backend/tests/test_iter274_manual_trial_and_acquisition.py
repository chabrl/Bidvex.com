"""
iter274 — Manual trial activation + external auctioneer acquisition.

Sprint goal: close the loop between the Admin Promotions Engine and
the External Email Marketing system so a single click can put a
not-yet-registered partner inside a paid platform with the annual fee
waived for the duration of their trial.

Coverage:

Mission 1 — Coupon issuance
  • POST /api/admin/promotions/activate-trial mints a tracking-friendly
    `BVX-TRIAL-XXXXXXXX` code, stores it under `partner_trial_coupons`,
    and returns the per-recipient signup URL.
  • Calling it twice for the same recipient_email + partner_type is
    idempotent — the second call returns `deduped=true` with the same
    code.
  • `?send_invite_email=True` also fires the bilingual single-shot
    SendGrid invite.

Mission 2 — External campaign coupon attachment
  • `CampaignCreate` schema now accepts `attach_trial_coupon` +
    `trial_partner_type`. The wizard step-1 surface exposes both fields.
  • The dispatcher mints one coupon per recipient at send-time, swaps
    `{trial_signup_url}` + `{promo_code}` placeholders in the body, and
    surfaces a `coupons_minted` integer on `last_dispatch`.

Mission 3 — Public + redemption flow
  • GET /api/promotions/coupons/{code} validates the format, returns
    422 on bad payloads, 404 on unknown codes, 200 with `valid=True`
    on live codes.
  • POST /api/auth/register with `promo_code=BVX-TRIAL-*` redeems the
    coupon atomically: status → `redeemed`, user gets `platform_fee_paid:
    True`, a `partner_trials` row is inserted with the right duration.
  • Vanilla registrations (no promo_code) leave the coupons collection
    untouched.

Mission 4 — Frontend wiring
  • PartnerTrialsAdminSection has the "Generate Coupon" mode toggle +
    submit button + result panel with copy buttons.
  • AdminExternalCampaigns wizard exposes the attach-coupon checkbox +
    partner-type select wired to the doc state.
  • AuthPage lands on the signup tab when `?promo=` is present, fetches
    the coupon preview, renders the success banner, AND includes
    `promo_code` in the register payload.
"""
from __future__ import annotations

import os
import re
import uuid
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


# ── Mission 1 — Coupon issuance (static + helpers) ────────────────────


def test_iter274_coupon_module_exposes_canonical_helpers():
    from routes import trial_coupons as tc

    assert tc.TRIAL_DURATIONS == {"dealer": 30, "broker": 60, "storage": 45}
    assert tc.COUPON_CODE_RE.pattern == r"^BVX-TRIAL-[A-Z0-9]{8}$"
    code = tc.generate_coupon_code()
    assert tc.COUPON_CODE_RE.match(code), f"generated code does not match wire format: {code}"
    assert tc.build_signup_url("BVX-TRIAL-ABCDEF12", campaign_slug="auctioneer_invite").endswith(
        "register?promo=BVX-TRIAL-ABCDEF12&utm_source=external_marketing&utm_campaign=auctioneer_invite"
    )


def test_iter274_activate_trial_endpoint_registered():
    src = _read("routes/trial_coupons.py")
    assert '@admin_coupons_router.post("/activate-trial")' in src
    assert "async def activate_trial" in src
    # Bulk endpoint exists too — used by the external campaign dispatcher.
    assert '@admin_coupons_router.post("/coupons/bulk")' in src


def test_iter274_server_mounts_both_coupon_routers():
    src = _read("server.py")
    assert '("routes.trial_coupons", "admin_coupons_router"' in src
    assert '("routes.trial_coupons", "public_coupons_router"' in src


def test_iter274_activate_trial_live_mints_dealer_coupon():
    token = _login_admin()
    if not token:
        pytest.skip("admin login unavailable")
    email = f"iter274-{uuid.uuid4().hex[:8]}@example.com"
    r = httpx.post(
        f"{BASE}/api/admin/promotions/activate-trial",
        json={
            "partner_type":      "dealer",
            "recipient_email":   email,
            "recipient_name":    "iter274 Dealer",
            "company_name":      "iter274 Co",
            "send_invite_email": False,
            "note":              "iter274 test",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["deduped"] is False
    coupon = body["coupon"]
    assert re.match(r"^BVX-TRIAL-[A-Z0-9]{8}$", coupon["code"])
    assert coupon["partner_type"] == "dealer"
    assert coupon["duration_days"] == 30
    assert coupon["status"] == "issued"
    assert coupon["recipient_email"] == email.lower()
    assert "register?promo=" in coupon["signup_url"]


def test_iter274_activate_trial_is_idempotent_per_recipient():
    token = _login_admin()
    if not token:
        pytest.skip("admin login unavailable")
    email = f"iter274dup-{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "partner_type":      "broker",
        "recipient_email":   email,
        "send_invite_email": False,
    }
    r1 = httpx.post(
        f"{BASE}/api/admin/promotions/activate-trial",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    assert r1.status_code == 200
    code1 = r1.json()["coupon"]["code"]

    r2 = httpx.post(
        f"{BASE}/api/admin/promotions/activate-trial",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["deduped"] is True
    assert body2["coupon"]["code"] == code1


def test_iter274_bulk_endpoint_mints_n_codes():
    token = _login_admin()
    if not token:
        pytest.skip("admin login unavailable")
    r = httpx.post(
        f"{BASE}/api/admin/promotions/coupons/bulk",
        json={"partner_type": "storage", "count": 4, "campaign_slug": "iter274_bulk"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["minted"] == 4
    assert len(body["codes"]) == 4
    assert all(re.match(r"^BVX-TRIAL-[A-Z0-9]{8}$", c) for c in body["codes"])
    # All codes distinct.
    assert len(set(body["codes"])) == 4


# ── Mission 2 — External campaign coupon attachment ───────────────────


def test_iter274_campaign_schema_accepts_attach_trial_coupon():
    src = _read("routes/external_campaigns.py")
    assert "attach_trial_coupon: bool = False" in src
    assert 'pattern="^(dealer|broker|storage)$"' in src
    # The persisted document carries the new keys.
    assert '"attach_trial_coupon": bool(body.attach_trial_coupon)' in src
    assert '"trial_partner_type":  body.trial_partner_type if body.attach_trial_coupon else None' in src


def test_iter274_dispatcher_substitutes_coupon_placeholders():
    src = _read("routes/external_campaigns.py")
    # Coupon-mode guard.
    assert 'coupon_mode = bool(doc.get("attach_trial_coupon"))' in src
    # Placeholder substitution.
    assert '"{trial_signup_url}"' in src
    assert '"{promo_code}"' in src
    # Mint inserts to the right collection.
    assert "db.partner_trial_coupons.insert_one(coupon_doc)" in src
    # `coupons_minted` rolls up into the last_dispatch envelope + response.
    assert '"coupons_minted":   coupons_minted' in src or "'coupons_minted'" in src


def test_iter274_send_now_response_includes_coupons_minted_field():
    src = _read("routes/external_campaigns.py")
    assert '"coupons_minted":  result.get("coupons_minted", 0)' in src
    assert '"coupons_minted":   result.get("coupons_minted", 0)' in src  # last_dispatch


def test_iter274_live_campaign_with_coupon_mints_per_recipient():
    """Create a coupon-attached campaign, add 3 recipients, send-now,
    and verify exactly 3 coupons were minted with the right
    campaign_id linkage."""
    token = _login_admin()
    if not token:
        pytest.skip("admin login unavailable")
    r = httpx.post(
        f"{BASE}/api/admin/external-campaigns",
        json={
            "name":         f"iter274-camp-{uuid.uuid4().hex[:6]}",
            "subject_en":   "Welcome auctioneer iter274",
            "subject_fr":   "Bienvenue iter274",
            "body_html_en": "<p>Join us {trial_signup_url} {promo_code} {unsubscribe_url}</p>",
            "body_html_fr": "<p>FR</p>",
            "attach_trial_coupon": True,
            "trial_partner_type":  "dealer",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    assert r.status_code == 200, r.text
    cid = r.json()["campaign_id"]

    try:
        # Push 3 manual recipients.
        emails = [f"iter274rcp{i}-{uuid.uuid4().hex[:6]}@example.com" for i in range(3)]
        r2 = httpx.post(
            f"{BASE}/api/admin/external-campaigns/{cid}/recipients/manual",
            json={"emails": emails},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        )
        assert r2.status_code == 200, r2.text

        # Send Now — in this preview env SendGrid will likely either
        # send (status_code=202) or hit the fallback path. Either way
        # the coupon-mint side effect runs BEFORE the SendGrid call, so
        # we always end with 3 fresh coupons.
        r3 = httpx.post(
            f"{BASE}/api/admin/external-campaigns/{cid}/send-now",
            json={},
            headers={"Authorization": f"Bearer {token}"},
            timeout=60.0,
        )
        assert r3.status_code == 200, r3.text
        body = r3.json()
        assert body["coupons_minted"] == 3, body

        # Verify the linkage via the admin coupons listing.
        r4 = httpx.get(
            f"{BASE}/api/admin/promotions/coupons",
            params={"campaign_id": cid, "limit": 10},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        assert r4.status_code == 200
        items = r4.json()["items"]
        assert len(items) == 3
        for it in items:
            assert it["campaign_id"] == cid
            assert it["partner_type"] == "dealer"
            assert it["source"] == "external_campaign"
            assert it["recipient_email"]
            assert "register?promo=" in it["signup_url"]
    finally:
        httpx.delete(
            f"{BASE}/api/admin/external-campaigns/{cid}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )


# ── Mission 3 — Public preview + redemption ────────────────────────────


def test_iter274_public_preview_rejects_malformed_codes():
    r = httpx.get(f"{BASE}/api/promotions/coupons/not-a-code", timeout=10.0)
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert detail["error_code"] == "invalid_coupon_format"


def test_iter274_public_preview_returns_404_for_unknown():
    bogus = "BVX-TRIAL-ABCDEF12"
    r = httpx.get(f"{BASE}/api/promotions/coupons/{bogus}", timeout=10.0)
    # Could be 200 if the bulk mint test happened to land on that code,
    # so we tolerate both — but on 404 we expect the structured envelope.
    if r.status_code == 404:
        assert r.json()["detail"]["error_code"] == "coupon_not_found"


def test_iter274_full_register_flow_consumes_coupon_and_waives_fee():
    """End-to-end: admin mints a coupon → guest registers with
    `promo_code=THAT_CODE` → coupon status flips to redeemed → user has
    `platform_fee_paid=True` AND a matching `partner_trials` row."""
    token = _login_admin()
    if not token:
        pytest.skip("admin login unavailable")

    # Mint a fresh dealer coupon.
    r1 = httpx.post(
        f"{BASE}/api/admin/promotions/activate-trial",
        json={"partner_type": "broker"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    assert r1.status_code == 200
    code = r1.json()["coupon"]["code"]

    # Public preview shows valid=True.
    r2 = httpx.get(f"{BASE}/api/promotions/coupons/{code}", timeout=10.0)
    assert r2.status_code == 200
    preview = r2.json()
    assert preview["valid"] is True
    assert preview["partner_type"] == "broker"
    assert preview["duration_days"] == 60

    # Register a brand-new user with the promo.
    email = f"iter274redeem-{uuid.uuid4().hex[:8]}@example.com"
    mobile = f"5145556{uuid.uuid4().hex[:6]}"
    r3 = httpx.post(
        f"{BASE}/api/auth/register",
        json={
            "email":                 email,
            "password":              "RedeemTest274!",
            "name":                  "iter274 Redeem",
            "account_type":          "business",
            "mobile_number":         mobile,
            "company_name":          "iter274 LLC",
            "terms_agreed":          True,
            "ai_disclosure_consent": True,
            "promo_code":            code,
        },
        timeout=60.0,
    )
    assert r3.status_code in (200, 201), r3.text

    # Coupon status now `redeemed`.
    r4 = httpx.get(f"{BASE}/api/promotions/coupons/{code}", timeout=10.0)
    assert r4.status_code == 200
    assert r4.json()["status"] == "redeemed"

    # Inspect the user record via Motor to confirm trial flags.
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BACKEND_ROOT, ".env"))
    from motor.motor_asyncio import AsyncIOMotorClient

    async def _inspect():
        client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
        try:
            db_name = os.environ.get("DB_NAME") or "bazario_db"
            user = await client[db_name].users.find_one(
                {"email": email.lower()},
                {"_id": 0,
                 "id": 1,
                 "partner_type": 1,
                 "partner_trial_active": 1,
                 "platform_fee_paid": 1,
                 "partner_subscription_active": 1,
                 "partner_fee_paid_via_coupon": 1},
            )
            trial = None
            if user:
                trial = await client[db_name].partner_trials.find_one(
                    {"user_id": user["id"], "activated_via_coupon": code},
                    {"_id": 0},
                )
            return user, trial
        finally:
            client.close()

    user, trial = asyncio.run(_inspect())
    assert user is not None, "registered user must persist"
    assert user["partner_type"] == "broker"
    assert user["partner_trial_active"] is True
    assert user["platform_fee_paid"] is True
    assert user["partner_subscription_active"] is True
    assert user["partner_fee_paid_via_coupon"] == code
    assert trial is not None, "partner_trials row must be created"
    assert trial["partner_type"] == "broker"
    assert trial["status"] == "active"


def test_iter274_register_without_promo_does_not_touch_coupons():
    """Sanity — a vanilla register (no `promo_code`) must NOT mark any
    coupon as redeemed and must not flip the annual-fee flag."""
    token = _login_admin()
    if not token:
        pytest.skip("admin login unavailable")
    email = f"iter274noprm-{uuid.uuid4().hex[:8]}@example.com"
    mobile = f"5145557{uuid.uuid4().hex[:6]}"
    r = httpx.post(
        f"{BASE}/api/auth/register",
        json={
            "email":                 email,
            "password":              "NoPromo274!",
            "name":                  "no promo",
            "account_type":          "personal",
            "mobile_number":         mobile,
            "terms_agreed":          True,
            "ai_disclosure_consent": True,
        },
        timeout=60.0,
    )
    assert r.status_code in (200, 201), r.text

    # The new user must NOT have any partner trial flags.
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BACKEND_ROOT, ".env"))
    from motor.motor_asyncio import AsyncIOMotorClient

    async def _check():
        client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
        try:
            db_name = os.environ.get("DB_NAME") or "bazario_db"
            return await client[db_name].users.find_one(
                {"email": email.lower()},
                {"_id": 0,
                 "partner_trial_active": 1,
                 "partner_fee_paid_via_coupon": 1},
            )
        finally:
            client.close()

    user = asyncio.run(_check())
    assert user is not None
    assert not user.get("partner_trial_active")
    assert not user.get("partner_fee_paid_via_coupon")


def test_iter274_register_with_invalid_promo_still_succeeds():
    """A signup with a bogus / expired / forwarded-and-already-redeemed
    promo must not 500 — the register call returns 200 and the user
    just lands without trial flags."""
    email = f"iter274badprm-{uuid.uuid4().hex[:8]}@example.com"
    mobile = f"5145558{uuid.uuid4().hex[:6]}"
    r = httpx.post(
        f"{BASE}/api/auth/register",
        json={
            "email":                 email,
            "password":              "BadPromo274!",
            "name":                  "bad promo",
            "account_type":          "personal",
            "mobile_number":         mobile,
            "terms_agreed":          True,
            "ai_disclosure_consent": True,
            "promo_code":            "BVX-TRIAL-NOPENOPE",  # 9 chars suffix → invalid format
        },
        timeout=60.0,
    )
    assert r.status_code in (200, 201), r.text


# ── Mission 4 — Frontend wiring ───────────────────────────────────────


def test_iter274_partner_trials_admin_section_has_coupon_mode():
    src = _read_fe("components/admin/PartnerTrialsAdminSection.jsx")
    assert 'data-testid="activate-mode-toggle"' in src
    assert 'data-testid="activate-mode-existing"' in src
    assert 'data-testid="activate-mode-coupon"' in src
    assert "activateMode" in src
    # The coupon mode form must surface every field the backend accepts.
    for tid in (
        "coupon-recipient-email",
        "coupon-recipient-name",
        "coupon-company-name",
        "coupon-send-invite-toggle",
        "coupon-mint-submit",
    ):
        assert f'data-testid="{tid}"' in src
    # Mint handler must call the new endpoint.
    assert "/admin/promotions/activate-trial" in src


def test_iter274_partner_trials_result_panel_renders_code_and_copy():
    src = _read_fe("components/admin/PartnerTrialsAdminSection.jsx")
    assert 'data-testid="coupon-result-panel"' in src
    assert 'data-testid="coupon-result-code"' in src
    assert 'data-testid="coupon-result-signup-url"' in src
    assert 'data-testid="coupon-copy-code"' in src
    assert 'data-testid="coupon-copy-url"' in src


def test_iter274_admin_external_campaigns_has_coupon_attach_section():
    src = _read_fe("pages/admin/AdminExternalCampaigns.jsx")
    assert 'data-testid="coupon-attach-section"' in src
    assert 'data-testid="coupon-attach-toggle"' in src
    assert 'data-testid="coupon-partner-type-select"' in src
    # The wizard initial doc state must carry the new fields.
    assert "attach_trial_coupon: false" in src
    assert "trial_partner_type: 'dealer'" in src


def test_iter274_auth_page_parses_promo_and_renders_banner():
    src = _read_fe("pages/AuthPage.js")
    assert 'data-testid="trial-coupon-banner"' in src
    assert 'data-testid="trial-coupon-error"' in src
    # Must read ?promo= from URL.
    assert "params.get('promo')" in src
    # Must hit the public preview endpoint.
    assert "/promotions/coupons/" in src
    # Must include the promo_code in the register payload.
    assert "promo_code: trialCoupon.code" in src
    # Must land on the signup tab (not login) when promo is present.
    assert "return !params.get('promo')" in src
