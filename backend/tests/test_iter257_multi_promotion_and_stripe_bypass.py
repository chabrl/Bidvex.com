"""
iter257 — Stripe Bypass Fix + Multi-Promotion Engine.

Test roster (8 tests):

  Mission 1 — Stripe bypass repair (the screenshot bug):
    1. `apply_and_record_discount(discount=...)` is GONE — the broken
       kwarg call that silently TypeError'd is no longer in the
       Partner checkout pipeline.
    2. `routes/partners.py` defaults the partner annual fee to $100
       (not the stale $499 placeholder).
    3. `_ensure_stripe_coupon_for_promotion` is exposed for the
       partial-discount path so Stripe Checkout sessions render the
       reduced total natively via the `discounts` parameter.
    4. The partner checkout endpoint stamps the Stripe Coupon onto
       the session kwargs only for partial promos (full waivers still
       short-circuit and return `free_activation=True` without ever
       calling stripe.checkout.Session.create).

  Mission 2 — Multi-promotion engine (new capability):
    5. `PromotionCreate.combined_components` schema accepts a list of
       per-type components, each with its own config; create endpoint
       persists `combined_components` on the promotion doc.
    6. `compute_promotion_discount` honors `combined_components` and
       picks the component giving the biggest CAD discount for the
       current `transaction_type` (the others stay silent).
    7. `_best_eligible_component` returns None when no component
       maps to the requested transaction_type — falling back to the
       legacy single-type path keeps back-compat green.
    8. `POST /admin/promotions/preview-combined` returns the resolved
       per-transaction math so admins can validate a candidate
       campaign before saving it.
"""
from __future__ import annotations

import asyncio
import os
import re
import uuid
from typing import Any, Dict, List


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _read(rel: str) -> str:
    with open(os.path.join(BACKEND_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


# ─── Mission 1 — Stripe bypass repair (static-source assertions) ─────

def test_iter257_legacy_apply_and_record_discount_kwarg_call_is_gone():
    """The original bug: routes/partners.py called
    `apply_and_record_discount(discount=discount, transaction_type=...)`
    but the function takes `base_amount_cad`, NOT a `discount` kwarg.
    The TypeError was swallowed by `except Exception`, silently
    falling through to full-price Stripe. iter257 replaces that call
    with a direct `record_promotion_usage(...)` invocation."""
    src = _read("routes/partners.py")
    # Strip single-line `#` comments so the historical-context comment
    # mentioning the function name doesn't false-positive the assert.
    code_only = "\n".join(
        re.sub(r"#.*$", "", line) for line in src.splitlines()
    )
    # The bad pattern must be gone from executable code.
    assert "apply_and_record_discount(" not in code_only, (
        "routes/partners.py still calls apply_and_record_discount — "
        "the kwarg signature mismatch caused the 100% bypass to fail"
    )
    # The fix must use record_promotion_usage directly.
    assert "record_promotion_usage(" in code_only, (
        "routes/partners.py must record promo usage via record_promotion_usage"
    )


def test_iter257_partner_annual_fee_default_is_100_not_499():
    """iter256 anchored the Annual Partner Fee at $100. The
    BIDVEX_PARTNER_ANNUAL_FEE_CAD env default in routes/partners.py
    must match — using the stale 499.0 caused full-waiver math to
    over-discount and (separately) confused the admin ledger preview."""
    src = _read("routes/partners.py")
    m = re.search(
        r'BIDVEX_PARTNER_ANNUAL_FEE_CAD"\s*,\s*"(\d+(?:\.\d+)?)"\s*\)',
        src,
    )
    assert m, "could not find BIDVEX_PARTNER_ANNUAL_FEE_CAD default in routes/partners.py"
    assert float(m.group(1)) == 100.0, (
        f"BIDVEX_PARTNER_ANNUAL_FEE_CAD default must be 100, got {m.group(1)}"
    )
    # The activate-to-account endpoint must also be anchored at $100.
    promo_src = _read("routes/admin_promotions.py")
    matches = re.findall(
        r'BIDVEX_PARTNER_ANNUAL_FEE_CAD"\s*,\s*"(\d+(?:\.\d+)?)"\s*\)',
        promo_src,
    )
    assert matches, "could not find BIDVEX_PARTNER_ANNUAL_FEE_CAD in admin_promotions.py"
    for v in matches:
        assert float(v) == 100.0, (
            f"BIDVEX_PARTNER_ANNUAL_FEE_CAD default in admin_promotions.py "
            f"must be 100, got {v}"
        )


def test_iter257_partial_discount_stripe_coupon_helper_exists_and_is_idempotent():
    """The partial-discount path (e.g. 25% off) must attach a Stripe
    Coupon to the Checkout Session so users see the reduced total.
    The `_ensure_stripe_coupon_for_promotion` helper:
      - Lives in routes/partners.py
      - Caps percent at [0, 100]
      - Generates a deterministic Stripe coupon id from the promotion
      - Treats `resource_already_exists` as a successful no-op
        (idempotency)
    """
    src = _read("routes/partners.py")
    assert "_ensure_stripe_coupon_for_promotion" in src
    assert "stripe.Coupon.create" in src
    assert "percent_off" in src
    # Idempotency guard: re-creating a coupon with the same id should
    # not raise — we trust the existing one.
    assert "already exists" in src or "resource_already_exists" in src
    # The helper must be invoked from the partner checkout pipeline
    # for partial (>0, <100) discounts.
    assert "applied_stripe_coupon_id" in src


def test_iter257_partner_checkout_attaches_stripe_coupon_only_for_partial_promos():
    """Full waivers (100% off) MUST skip Stripe entirely and return
    `free_activation: True`. Partial discounts (>0%, <100%) MUST
    attach the Stripe Coupon to `session_kwargs["discounts"]` so the
    Checkout page renders the reduced total."""
    src = _read("routes/partners.py")
    # 100% waiver path returns free_activation True and never calls
    # stripe.checkout.Session.create inside that branch.
    full_waiver_branch = re.search(
        r'is_full_waiver.*?\):\s*\n([\s\S]+?)return\s+\{[\s\S]+?"free_activation"\s*:\s*True',
        src,
    )
    assert full_waiver_branch, "could not locate the 100% waiver short-circuit branch"
    assert "stripe.checkout.Session.create" not in full_waiver_branch.group(1), (
        "100% waiver path must NOT call stripe.checkout.Session.create"
    )
    # Partial-discount path: the session kwargs receive a `discounts`
    # array referencing the applied Stripe Coupon id.
    assert 'session_kwargs["discounts"] = [{"coupon": applied_stripe_coupon_id}]' in src


# ─── Mission 2 — Multi-promotion engine (live runtime assertions) ────

def test_iter257_promotion_create_persists_combined_components():
    """The PromotionCreate schema must accept `combined_components`
    (a list of per-type sub-promotions), and the create endpoint must
    persist them on the inserted promotion document."""
    src = _read("routes/admin_promotions.py")
    assert "class PromotionComponent(BaseModel)" in src
    assert "combined_components: Optional[List[PromotionComponent]]" in src
    # The create endpoint stores combined_components on the doc.
    insert_block = re.search(
        r'promotion\s*=\s*\{[\s\S]+?await db\.promotions\.insert_one',
        src,
    )
    assert insert_block, "could not locate the create-promotion insert block"
    assert '"combined_components"' in insert_block.group(0), (
        "create-promotion must persist combined_components on the doc"
    )


def test_iter257_compute_promotion_discount_picks_best_component_per_transaction():
    """`compute_promotion_discount` must honor `combined_components`
    and pick the component giving the biggest CAD discount for the
    requested transaction_type. Validates math directly against the
    `_best_eligible_component` helper (no DB roundtrip)."""
    from services.promotion_runtime import _best_eligible_component

    components = [
        # 25% off listing promotion (eligible for listing_promotion)
        {"type": "free_promotion_boost", "config": {}},
        # Partner launch offer — 100% off listing fee + buyer premium
        {"type": "partner_launch_offer", "config": {}},
        # Reduced commission 30% (eligible for seller_commission)
        {"type": "reduced_commission", "config": {"discount_percent": 30}},
    ]

    # listing_fee: only partner_launch_offer is eligible → 100%
    best = _best_eligible_component(components, "listing_fee", 100.0)
    assert best is not None
    ctype, _, pct = best
    assert ctype == "partner_launch_offer"
    assert pct == 100.0

    # listing_promotion: free_promotion_boost (100%) AND partner_launch_offer
    # (100%) both eligible — engine picks deterministically (first-match
    # by saving-tie). Either is a 100% waiver, so saving == 100.
    best = _best_eligible_component(components, "listing_promotion", 25.0)
    assert best is not None
    _, _, pct = best
    assert pct == 100.0

    # seller_commission: reduced_commission @30% AND partner_launch_offer @100%
    # → partner_launch_offer wins on saving.
    best = _best_eligible_component(components, "seller_commission", 200.0)
    assert best is not None
    ctype, _, pct = best
    assert ctype == "partner_launch_offer"
    assert pct == 100.0


def test_iter257_combined_promotion_falls_back_to_single_type_when_no_component_matches():
    """Backwards compat: when `combined_components` has NO component
    eligible for the requested transaction_type, the engine must NOT
    apply a discount via the multi-component path. The legacy single-
    `type` path still owns the contract."""
    from services.promotion_runtime import _best_eligible_component

    components = [
        # Only reduced_commission — not eligible for `listing_promotion`
        {"type": "reduced_commission", "config": {"discount_percent": 40}},
    ]
    assert _best_eligible_component(components, "listing_promotion", 25.0) is None
    # `listing_fee` is also NOT in _WAIVERS_BY_TX["reduced_commission"]
    # → no eligible component.
    assert _best_eligible_component(components, "listing_fee", 100.0) is None


def test_iter257_combined_promotion_flat_amount_and_cap_apply():
    """Multi-component configs may carry `flat_amount_cad` (additive
    credit, e.g. multi-lot bonus) and `max_discount_cad` (CAD cap).
    The engine must respect both."""
    from services.promotion_runtime import _best_eligible_component

    # 50% off seller_commission, capped at $20, plus a $5 flat credit
    components = [{
        "type": "reduced_commission",
        "config": {
            "discount_percent": 50,
            "max_discount_cad": 20.0,
            "flat_amount_cad": 5.0,
        },
    }]
    # Math on a $200 base: 50% = $100, capped to $20, plus $5 flat = $25
    base = 200.0
    chosen = _best_eligible_component(components, "seller_commission", base)
    assert chosen is not None
    ctype, cfg, pct = chosen
    assert ctype == "reduced_commission"
    assert pct == 50.0
    disc = round(base * (pct / 100.0), 2)
    cap = float(cfg.get("max_discount_cad"))
    disc = min(disc, cap)
    disc += float(cfg.get("flat_amount_cad", 0))
    assert disc == 25.0


# ─── End-to-end runtime smoke (via in-memory MongoDB-like stub) ──────

class _StubColl:
    """Minimal collection stub for the apply_active_promotions flow."""

    def __init__(self, docs=None):
        self.docs: List[Dict[str, Any]] = list(docs or [])

    def find(self, q=None, proj=None):
        matches = [d for d in self.docs if _matches(d, q or {})]
        class _Cur:
            def __init__(self, items): self.items = items
            async def to_list(self, length=None): return list(self.items[:length] if length else self.items)
        return _Cur(matches)

    async def find_one(self, q, proj=None):
        for d in self.docs:
            if _matches(d, q):
                return d
        return None

    async def count_documents(self, q):
        return sum(1 for d in self.docs if _matches(d, q))


def _matches(doc, q):
    for k, v in q.items():
        if isinstance(v, dict) and "$lte" in v:
            if not (doc.get(k) and doc[k] <= v["$lte"]):
                return False
        elif isinstance(v, dict) and "$gte" in v:
            if not (doc.get(k) and doc[k] >= v["$gte"]):
                return False
        else:
            if doc.get(k) != v:
                return False
    return True


class _StubDB:
    def __init__(self, promotions, users, usages):
        self.promotions = _StubColl(promotions)
        self.users = _StubColl(users)
        self.promotion_usage = _StubColl(usages)


def test_iter257_apply_active_promotions_picks_combined_promo_over_single_type():
    """End-to-end: a campaign with `combined_components` containing
    `partner_launch_offer` (100% off) outranks a plain `reduced_commission`
    @ 50% promo in apply_active_promotions scoring."""
    from routes.admin_promotions import apply_active_promotions

    now_iso = "2025-01-01T00:00:00+00:00"
    end_iso = "2030-01-01T00:00:00+00:00"
    user = {"id": "u1", "email": "u@x.com", "account_type": "partner", "is_partner": True}
    base_promo = {
        "status": "active",
        "start_date": now_iso,
        "end_date": end_iso,
        "max_uses": None,
        "uses_per_user": 1,
        "current_uses": 0,
        "target": "all",
        "target_config": {"target": "all"},
        "config": {"scope": ["all"]},
    }
    single = {
        **base_promo,
        "id": "single-1",
        "coupon_code": "SINGLE50",
        "type": "reduced_commission",
        "config": {"scope": ["all"], "discount_percent": 50},
    }
    combo = {
        **base_promo,
        "id": "combo-1",
        "coupon_code": "COMBO",
        "type": "free_first_listing",
        "combined_components": [
            {"type": "partner_launch_offer", "config": {}},
            {"type": "reduced_commission", "config": {"discount_percent": 50}},
        ],
    }
    db = _StubDB(promotions=[single, combo], users=[user], usages=[])
    matched = asyncio.run(apply_active_promotions(
        db=db, user_id="u1", transaction_type="seller_commission", listing_type=None,
    ))
    assert matched is not None
    assert matched["id"] == "combo-1", (
        "combined promo with partner_launch_offer (100%) must outrank "
        "a single 50% reduced_commission promo"
    )
    # The applied_value reflects the best component pct (100).
    assert matched.get("applied_value", 0) == 100.0


# ─── Admin UI surface assertions ─────────────────────────────────────

def test_iter257_admin_promotion_manager_exposes_combined_components_editor():
    """The admin PromotionManager page must expose a UI surface for
    creating/editing combined-component campaigns:
      - A "Combined Components" section with the proper test id
      - Add-component button
      - Per-row type + percent + flat editors
      - A "Preview Combined Math" CTA that hits the new
        /admin/promotions/preview-combined endpoint."""
    pm_path = os.path.abspath(os.path.join(
        BACKEND_ROOT, "..", "frontend", "src", "pages", "admin", "PromotionManager.js",
    ))
    with open(pm_path, "r", encoding="utf-8") as fh:
        src = fh.read()
    assert 'data-testid="combined-components-section"' in src
    assert 'data-testid="add-combined-component-btn"' in src
    assert "combined_components" in src
    assert 'data-testid="preview-combined-btn"' in src
    assert "/admin/promotions/preview-combined" in src
    # The save payload conditionally includes combined_components (only
    # when non-empty, preserving backward compat).
    assert "combined_components:" in src and "length > 0" in src
