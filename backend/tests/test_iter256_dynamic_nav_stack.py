"""
iter256 — Dynamic Nav Stack tests.

Verifies the new layout architecture that replaces the legacy
`pt-16` / `pt-20` per-page hotfixes:

  1. `PromoBannerContext` exists, exposes a `PromoBannerProvider`
     React component AND a `useBannerHeight()` hook, and is wired into
     the global provider tree in `App.js`.

  2. The `PromotionalBanner` component is fixed at `top-0` with
     `z-[80]` (above the navbar's `z-[70]`), measures its own height
     via `ResizeObserver`, and pushes that height into the context so
     the dismiss `X` button remains fully clickable on every viewport.

  3. The `Navbar` consumes `useBannerHeight()` and binds its fixed
     `top` AND the post-nav spacer to that dynamic value, so the red
     promo banner can never be trapped behind the white nav header
     and the page content auto-clears the combined stack.
"""
from __future__ import annotations

import os
import re


FRONTEND = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src")
)


def _read(rel: str) -> str:
    with open(os.path.join(FRONTEND, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def test_iter256_promo_banner_context_provider_and_hook_are_exported_and_wired():
    """PromoBannerContext must define a Provider, a `useBannerHeight`
    hook, AND be mounted inside App.js so every route inherits it."""
    ctx_src = _read("contexts/PromoBannerContext.js")
    assert "export const PromoBannerProvider" in ctx_src, (
        "PromoBannerProvider must be a named React component export"
    )
    assert "export const useBannerHeight" in ctx_src, (
        "useBannerHeight must be a named hook export"
    )
    # The provider stores the bannerHeight state.
    assert "setBannerHeight" in ctx_src and "useState" in ctx_src, (
        "Provider must back bannerHeight with React state"
    )

    app_src = _read("App.js")
    assert "PromoBannerProvider" in app_src, (
        "App.js must import + mount <PromoBannerProvider>"
    )
    # The provider must wrap the rendered tree (not just imported).
    assert "<PromoBannerProvider>" in app_src and "</PromoBannerProvider>" in app_src


def test_iter256_promo_banner_is_fixed_at_z80_above_nav_and_measures_height():
    """The red promo banner stack MUST be `fixed top-0` with `z-[80]`
    (the nav lives at `z-[70]`), AND must measure its rendered height
    via ResizeObserver to drive the dynamic stack."""
    src = _read("components/PromotionalBanner.jsx")

    # The stack `<div>` must declare the fixed + z-80 + top-0 trio in
    # its className. (Order-independent string contains is enough.)
    stack_div = re.search(
        r'<div[\s\S]{0,400}?data-testid=["\']promotional-banner-stack["\']',
        src,
    )
    assert stack_div, "could not find <div ... data-testid=promotional-banner-stack>"
    chunk = stack_div.group(0)
    assert "fixed" in chunk, "banner stack must be position: fixed"
    assert "top-0" in chunk, "banner stack must anchor at top-0"
    assert "z-[80]" in chunk, "banner stack must sit at z-[80] (above nav z-[70])"

    # The component must use ResizeObserver + setBannerHeight from
    # PromoBannerContext to keep the height live.
    assert "ResizeObserver" in src, (
        "PromotionalBanner must observe rendered height via ResizeObserver"
    )
    assert "usePromoBanner" in src or "useBannerHeight" in src, (
        "PromotionalBanner must consume PromoBannerContext"
    )
    assert "setBannerHeight" in src, (
        "PromotionalBanner must push measured height into the context"
    )


def test_iter256_navbar_binds_top_to_banner_height_and_spacer_absorbs_it():
    """The fixed Navbar must read `useBannerHeight()` from
    PromoBannerContext and bind both its own `top` style AND the
    post-nav spacer marginTop to that value. This is the dynamic
    stack that replaces all hardcoded `pt-16` / `pt-20` hotfixes."""
    src = _read("components/Navbar.js")

    # Hook import + usage.
    assert "useBannerHeight" in src, (
        "Navbar must import + use useBannerHeight()"
    )
    assert "PromoBannerContext" in src, (
        "Navbar must source the hook from PromoBannerContext"
    )

    # The fixed <nav> must bind its `top` to `${bannerHeight}px`.
    nav_top = re.search(
        r"style=\{\{\s*top:\s*`?\$\{bannerHeight\}px`?\s*\}\}",
        src,
    )
    assert nav_top, (
        "Navbar <nav> must declare style={{ top: `${bannerHeight}px` }}"
    )

    # The fixed nav class must no longer hardcode `top-0` — the
    # dynamic style drives the offset.
    main_nav_match = re.search(
        r'className=\{`fixed[^`]*`\}\s*style=\{\{\s*top:\s*`\$\{bannerHeight\}px`',
        src,
    )
    assert main_nav_match, (
        "Navbar must declare `fixed left-0 right-0 z-[70]` and rely on the "
        "dynamic style={{ top: `${bannerHeight}px` }} prop — no hardcoded `top-0`"
    )
    assert "top-0" not in main_nav_match.group(0), (
        "Navbar must NOT hardcode `top-0` — the dynamic style owns the offset"
    )

    # The post-nav spacer must absorb the banner height via marginTop
    # so page content clears the combined banner + nav stack without
    # any per-page padding hotfix.
    spacer_match = re.search(
        r'data-testid=["\']navbar-spacer["\']',
        src,
    )
    assert spacer_match, "Navbar must expose data-testid=navbar-spacer"
    spacer_div = re.search(
        r'<div[\s\S]{0,400}?data-testid=["\']navbar-spacer["\']',
        src,
    )
    assert spacer_div
    schunk = spacer_div.group(0)
    assert "marginTop" in schunk and "bannerHeight" in schunk, (
        "navbar-spacer must bind marginTop to bannerHeight"
    )
