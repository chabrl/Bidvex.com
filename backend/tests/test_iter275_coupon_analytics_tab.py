"""
iter275 — Coupon Conversion Analytics tab verification.

The tab is mounted inside the Admin Promotions Engine, immediately
below the Partner Trial Offers section. It is data-only frontend
work — no new backend models, schemas, or endpoints. All metrics are
computed client-side by joining the two existing endpoints:

    GET /api/admin/promotions/coupons       (iter274)
    GET /api/admin/external-campaigns       (iter271)

Coverage:

Mission 1 — Mount + wiring
  • `CouponAnalyticsTab.jsx` exists and is imported by PromotionManager.
  • The tab declares the `coupon-analytics-tab` root testid AND the
    four KPI cards + three sub-tab triggers.

Mission 2 — Conversion charting
  • The component reads from `/admin/promotions/coupons` and
    `/admin/external-campaigns` in parallel via Promise.all.
  • The subject A/B table renders the canonical funnel columns
    (Minted, Delivered, Opened, Clicked, Redeemed, Mint→Redeem %,
    Click→Redeem %, Avg Latency) with the testid'd redemption-rate
    cell pinned per campaign id.

Mission 3 — Performance comparison + chart
  • Recharts BarChart compares minted vs redeemed per campaign in a
    horizontal layout.
  • Rows are sorted by redemption_rate_pct DESC so the winning
    subjects float to the top.

Mission 4 — Defensive math + filter UI
  • `safePct(num, denom)` guards divide-by-zero.
  • Partner-type filter dropdown sub-selects dealer / broker / storage.
"""
from __future__ import annotations

import os
import re

import pytest


FRONTEND_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src"),
)


def _read_fe(rel: str) -> str:
    with open(os.path.join(FRONTEND_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


# ── Mission 1 — Mount + wiring ────────────────────────────────────────


def test_iter275_component_file_exists():
    fp = os.path.join(FRONTEND_ROOT, "components", "admin", "CouponAnalyticsTab.jsx")
    assert os.path.isfile(fp), f"CouponAnalyticsTab.jsx missing at {fp}"


def test_iter275_promotion_manager_imports_and_mounts_tab():
    src = _read_fe("pages/admin/PromotionManager.js")
    assert "import CouponAnalyticsTab" in src
    # Must be rendered, not just imported.
    assert "<CouponAnalyticsTab token={token} />" in src
    # Must mount immediately under the partner-trial section so the
    # mint→analytics flow is visually contiguous.
    pt_idx = src.find("<PartnerTrialsAdminSection")
    ca_idx = src.find("<CouponAnalyticsTab")
    assert 0 < pt_idx < ca_idx, "CouponAnalyticsTab must render AFTER PartnerTrialsAdminSection"


def test_iter275_root_testid_and_header_present():
    src = _read_fe("components/admin/CouponAnalyticsTab.jsx")
    assert 'data-testid="coupon-analytics-tab"' in src
    assert "Coupon Conversion Analytics" in src
    # Header explains the funnel so admins know exactly what they're seeing.
    assert "minted" in src.lower()
    assert "redeemed" in src.lower()
    assert "clicked" in src.lower()


def test_iter275_four_kpi_cards_present():
    src = _read_fe("components/admin/CouponAnalyticsTab.jsx")
    for tid in (
        "kpi-total-minted",
        "kpi-total-redeemed",
        "kpi-active-campaigns",
        "kpi-revoked",
    ):
        assert f'testid="{tid}"' in src, f"missing KPI card: {tid}"
    # Each KPI card also exposes a `<testid>-value` so tests can assert
    # the numeric payload without parsing the whole DOM.
    assert "testid={`${testid}-value`}" in src


def test_iter275_three_subtab_triggers():
    src = _read_fe("components/admin/CouponAnalyticsTab.jsx")
    for tid in (
        "coupon-analytics-tab-comparison",
        "coupon-analytics-tab-chart",
        "coupon-analytics-tab-timeline",
    ):
        assert f'data-testid="{tid}"' in src


# ── Mission 2 — Conversion charting (joins both endpoints) ────────────


def test_iter275_loads_coupons_and_campaigns_in_parallel():
    src = _read_fe("components/admin/CouponAnalyticsTab.jsx")
    # Promise.all over both admin endpoints — must NOT serialize.
    assert "Promise.all" in src
    assert "/admin/promotions/coupons" in src
    assert "/admin/external-campaigns" in src
    # Limit params raise the default ceiling so the page reflects the
    # full coupon population, not just the most recent 50.
    assert "limit: 500" in src
    assert "limit: 100" in src


def test_iter275_comparison_table_has_full_funnel_columns():
    src = _read_fe("components/admin/CouponAnalyticsTab.jsx")
    assert 'data-testid="coupon-analytics-comparison-table"' in src
    for col_header in ("Minted", "Delivered", "Opened", "Clicked", "Redeemed"):
        assert f">{col_header}<" in src, f"missing column header: {col_header}"
    # The two canonical ratios show up as explicit column headers.
    assert "Mint→Redeem %" in src
    assert "Click→Redeem %" in src


def test_iter275_per_campaign_redemption_rate_pinned_with_testid():
    src = _read_fe("components/admin/CouponAnalyticsTab.jsx")
    # Per-row redemption-rate cell uses a template-literal testid so a
    # spec test can target any specific campaign id.
    assert "data-testid={`coupon-redemption-rate-${r.campaign_id || 'manual'}`}" in src
    # Row-level testid so per-row assertions are stable.
    assert "data-testid={`coupon-row-${r.campaign_id || 'manual'}`}" in src


def test_iter275_aggregation_handles_manual_bucket():
    """Coupons without a `campaign_id` (manual mints from the
    PartnerTrialsAdminSection) must be bucketed under a synthetic
    "Manual / Direct" row so they still appear in the analytics."""
    src = _read_fe("components/admin/CouponAnalyticsTab.jsx")
    assert "Manual / Direct" in src
    assert "MANUAL_KEY" in src
    # Falls back to the `__manual__` key when campaign_id is null.
    assert "c.campaign_id || MANUAL_KEY" in src


def test_iter275_average_latency_metric_computed():
    """Average mint→redeem latency in hours per row — used by the
    Timeline view AND surfaced in the comparison table's last column."""
    src = _read_fe("components/admin/CouponAnalyticsTab.jsx")
    assert "redeem_latencies_hours" in src
    assert "avg_mint_to_redeem_hours" in src
    # The Mongo-style 'created_at' + 'redeemed_at' fields are the only
    # canonical anchors for latency arithmetic.
    assert "hoursBetween" in src
    assert "c.created_at, c.redeemed_at" in src


# ── Mission 3 — Performance comparison + bar chart ────────────────────


def test_iter275_recharts_bar_chart_present():
    src = _read_fe("components/admin/CouponAnalyticsTab.jsx")
    # The recharts import block must include BarChart + Bar + ResponsiveContainer.
    for sym in ("ResponsiveContainer", "BarChart", "Bar", "XAxis", "YAxis"):
        assert f" {sym}" in src or f"\n  {sym}" in src, f"recharts symbol missing: {sym}"
    assert 'data-testid="coupon-analytics-chart-container"' in src
    # Bar configuration must compare BOTH minted and redeemed.
    assert 'dataKey="minted"' in src
    assert 'dataKey="redeemed"' in src


def test_iter275_top_n_campaigns_charted_only():
    """Don't dump the entire 500-coupon population into the chart —
    slice to the top 10 by redemption rate for legibility."""
    src = _read_fe("components/admin/CouponAnalyticsTab.jsx")
    assert ".slice(0, 10)" in src
    # Manual bucket is explicitly excluded from the chart so the bars
    # only compare actual campaign performance.
    assert "filter((r) => r.campaign_id)" in src


def test_iter275_rows_sorted_by_redemption_rate_desc():
    src = _read_fe("components/admin/CouponAnalyticsTab.jsx")
    # Must sort by the canonical redemption_rate_pct DESC so winning
    # subjects float to the top of the side-by-side comparison.
    assert "b.redemption_rate_pct - a.redemption_rate_pct" in src


# ── Mission 4 — Defensive math + filter UI ────────────────────────────


def test_iter275_partner_type_filter_dropdown_present():
    src = _read_fe("components/admin/CouponAnalyticsTab.jsx")
    assert 'data-testid="coupon-analytics-partner-filter"' in src
    # All three partner types selectable.
    for opt in ('value="dealer"', 'value="broker"', 'value="storage"', 'value="all"'):
        assert opt in src, f"missing filter option: {opt}"


def test_iter275_safe_pct_guards_divide_by_zero():
    """The KPI strip and the table cells call `safePct` everywhere a
    ratio is shown. The helper must short-circuit on denom ≤ 0."""
    src = _read_fe("components/admin/CouponAnalyticsTab.jsx")
    # Helper present.
    assert re.search(r"const safePct\s*=\s*\([^)]*\)\s*=>", src), "safePct missing"
    # And it bails when denom is 0.
    assert "if (d <= 0) return 0;" in src
    # Both canonical conversion ratios use it.
    assert "redemption_rate_pct: safePct(b.redeemed, b.minted)" in src
    assert "click_to_redeem_pct: safePct(b.redeemed, b.clicked)" in src


def test_iter275_refresh_button_wired_to_loadAll():
    src = _read_fe("components/admin/CouponAnalyticsTab.jsx")
    assert 'data-testid="coupon-analytics-refresh"' in src
    # The button calls the same loader that the initial useEffect drives.
    assert "onClick={loadAll}" in src


def test_iter275_empty_state_messaging_present():
    """When there are NO coupons issued yet, the table renders a
    helpful empty-state message instead of a blank tbody."""
    src = _read_fe("components/admin/CouponAnalyticsTab.jsx")
    assert "No coupons issued yet" in src
    # The Partner Trial Offers card is referenced as the next-step CTA.
    assert "Partner Trial Offers" in src


# ── Mission 5 — Live HTTP smoke (data sources still healthy) ──────────


def test_iter275_data_endpoints_still_return_200():
    """End-to-end sanity that the two endpoints the tab depends on are
    still up and JSON-shaped the way the component reads them."""
    import httpx
    BASE = os.environ.get("E2E_BASE_URL", "http://localhost:8001")
    try:
        r = httpx.post(
            f"{BASE}/api/auth/login",
            json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
            timeout=8.0,
        )
    except Exception:
        pytest.skip("backend unreachable")
    if r.status_code != 200:
        pytest.skip("admin login unavailable in this env (likely rate-limited)")
    token = r.json().get("access_token") or r.json().get("token")
    headers = {"Authorization": f"Bearer {token}"}

    r1 = httpx.get(
        f"{BASE}/api/admin/promotions/coupons?limit=10",
        headers=headers,
        timeout=10.0,
    )
    assert r1.status_code == 200
    body1 = r1.json()
    assert "items" in body1 and isinstance(body1["items"], list)

    r2 = httpx.get(
        f"{BASE}/api/admin/external-campaigns?limit=10",
        headers=headers,
        timeout=10.0,
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert "campaigns" in body2 and isinstance(body2["campaigns"], list)
