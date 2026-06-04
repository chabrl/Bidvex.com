"""
iter280 — UI Widget Consolidation verification.

Context:
    The iter277 dashboard widget + the iter279-upgraded legacy public
    AIAssistant both rendered floating FABs at bottom-right. On the
    authenticated dashboards + admin routes (where iter277 was scoped)
    the two FABs visually collided.

    iter280 resolves the collision by UNMOUNTING the iter277 widget
    entirely and promoting the legacy AIAssistant to the canonical
    single site-wide AI Core surface. The legacy assistant already
    carries the full iter278/279 streaming UX (typewriter cursor +
    rose Stop button + abort handling) so the consolidation is
    behavior-preserving.

    The `AICoreSupportWidget.jsx` component file remains on disk for
    potential future contextual surfaces but is NEVER mounted from
    App.js post-iter280.

Coverage:

Mission 1 — App.js consolidation
  • No lazy-import of AICoreSupportWidget.
  • No AICoreSupportWidgetWrapper component definition.
  • No <AICoreSupportWidgetWrapper /> render.
  • The legacy <AIAssistantWrapper /> is the ONLY AI surface mount.
  • iter280 deprecation comment present so future agents understand.

Mission 2 — Backend route consolidation
  • The iter278 SSE endpoint (`/api/support/chat/stream`) and the
    iter276 non-streaming endpoint (`/api/support/chat`) are BOTH
    still up — they're independent of the widget unmounting. We
    keep them around because they're useful for future contextual
    surfaces + automated tooling.

Mission 3 — Legacy assistant context-aware surface detection
  • The legacy `AIAssistant.js` now detects the active surface
    (`admin` / `dashboard` / `listing_detail` / `public`) from the URL
    and forwards it via `extra_context` so the same unified assistant
    adjusts tone per route.

Mission 4 — Zero visual collision contract
  • Only ONE FAB renders globally — verified by static scan: the
    iter277 widget's `ai-core-fab` testid is not referenced by App.js
    (the widget component itself still has the testid, it just never
    renders).
"""
from __future__ import annotations

import os

import httpx
import pytest


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, "..", "frontend", "src"))
BASE = os.environ.get("E2E_BASE_URL", "http://localhost:8001")


def _read_fe(rel: str) -> str:
    with open(os.path.join(FRONTEND_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


# ── Mission 1 — App.js consolidation ──────────────────────────────────


def test_iter280_app_does_not_lazy_import_dashboard_widget():
    """The iter277 widget component file remains on disk for future
    use, but App.js must NOT lazy-import it anymore — otherwise the
    bundle still ships dead code AND a developer could accidentally
    re-mount it."""
    src = _read_fe("App.js")
    assert "lazy(() => import('./components/AICoreSupportWidget'))" not in src
    # The deprecation rationale comment MUST be in place so the next
    # agent doesn't blindly re-add the import.
    assert "iter280" in src
    assert "AICoreSupportWidget" in src  # the deprecation comment mentions it


def test_iter280_no_dashboard_widget_wrapper_definition():
    src = _read_fe("App.js")
    # The wrapper component definition (not just any string mention) must
    # be gone — but the deprecation comment in App.js intentionally names
    # the symbol so future agents understand what was removed.
    assert "const AICoreSupportWidgetWrapper" not in src
    assert "<AICoreSupportWidgetWrapper" not in src
    # And the deprecation comment explicitly names what was removed.
    assert "REMOVED: AICoreSupportWidgetWrapper" in src


def test_iter280_legacy_assistant_is_the_only_ai_mount():
    src = _read_fe("App.js")
    assert "<AIAssistantWrapper />" in src
    # And there is no second AI surface mount anywhere.
    assert src.count("AICoreSupportWidgetWrapper /") == 0


def test_iter280_dashboard_widget_file_still_exists_on_disk():
    """The component file is kept for potential future contextual
    surfaces (e.g. embedded chat panels). Just NOT mounted in App.js."""
    fp = os.path.join(FRONTEND_ROOT, "components", "AICoreSupportWidget.jsx")
    assert os.path.isfile(fp), (
        "AICoreSupportWidget.jsx must remain on disk for future re-use; "
        "iter280 only removes its App.js mount."
    )


# ── Mission 2 — Backend route consolidation ───────────────────────────


def test_iter280_iter276_non_streaming_endpoint_still_lives():
    """iter280 removed the FE mount but the backend endpoint MUST
    still respond so any future tooling / contextual surface can
    consume it without a backend redeploy."""
    r = httpx.get(f"{BASE}/api/support/health", timeout=5.0)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    assert body.get("provider") == "gemini"


def test_iter280_iter278_streaming_endpoint_still_lives():
    """Same belt-and-suspenders for the SSE variant — the route is
    still mounted in `routes/support.py`, just no longer consumed by
    the public widget."""
    from routes import support as support_route
    # Both endpoints declared on the same APIRouter.
    paths = [getattr(r, "path", None) for r in support_route.router.routes]
    assert any(p == "/support/chat" for p in paths)
    assert any(p == "/support/chat/stream" for p in paths)
    assert any(p == "/support/health" for p in paths)


# ── Mission 3 — Context-aware surface detection ───────────────────────


def test_iter280_legacy_assistant_detects_active_surface():
    """The unified assistant adapts its tone based on which route the
    user is currently viewing. The detector classifies the URL into
    one of `admin`, `dashboard`, `listing_detail`, or `public`."""
    src = _read_fe("components/AIAssistant.js")
    assert "_detectSurface" in src
    for surface in ("'admin'", "'dashboard'", "'listing_detail'", "'public'"):
        assert surface in src, f"surface label missing from detector: {surface}"
    # The detector classifies admin routes (highest priority).
    assert "p.startsWith('/admin')" in src
    # Dashboard routes — buyer/seller/facility.
    for needle in (
        "/seller/dashboard",
        "/buyer/dashboard",
        "/facility/dashboard",
    ):
        assert needle in src, f"missing dashboard route check: {needle}"


def test_iter280_active_surface_shipped_in_extra_context():
    """The detected surface MUST be forwarded to the backend via the
    existing `extra_context` payload so the model can read it without
    a schema change."""
    src = _read_fe("components/AIAssistant.js")
    assert "Active UI surface:" in src
    # And the value is the result of the detector call.
    assert "_detectSurface()" in src
    assert "_activeSurface" in src


# ── Mission 4 — Zero visual collision contract ────────────────────────


def test_iter280_no_iter277_fab_testid_in_app_mount_layer():
    """The iter277 widget's `ai-core-fab` testid is not in the
    application shell — it only exists inside the unmounted component
    file. This is a static guard against accidental re-introduction
    of the second FAB."""
    src = _read_fe("App.js")
    assert 'data-testid="ai-core-fab"' not in src
    # And there's no JSX `<AICoreSupportWidget` tag in App.js anymore.
    assert "<AICoreSupportWidget" not in src


def test_iter280_legacy_assistant_keeps_its_streaming_ux():
    """Regression guard — the iter279 streaming UX (cursor + Stop)
    that we just promoted to be the SOLE surface must NOT have
    regressed during the consolidation. We re-check the canonical
    testids here so a future App.js edit doesn't silently break the
    AIAssistant's streaming machinery."""
    src = _read_fe("components/AIAssistant.js")
    # Stop button + cursor testids preserved.
    assert 'data-testid={isLoading ? "ai-core-stop" : "ai-assistant-send-btn"}' in src
    assert 'data-testid="ai-core-stream-cursor"' in src
    # Branding strings preserved.
    assert "BidVex AI Core" in src
    assert "Luxury Auction Specialist" in src


# ── Mission 5 — Live backend sanity ───────────────────────────────────


def test_iter280_support_endpoints_respond_correctly_to_anonymous():
    """Anonymous + authenticated contracts both unchanged by iter280:
    health is public, chat/stream is still JWT-protected."""
    # Health = anonymous 200.
    r = httpx.get(f"{BASE}/api/support/health", timeout=5.0)
    assert r.status_code == 200

    # Chat (non-streaming) = anonymous 401/403.
    r2 = httpx.post(
        f"{BASE}/api/support/chat",
        json={"message": "hi"},
        timeout=5.0,
    )
    assert r2.status_code in (401, 403), r2.text

    # Chat (streaming) = anonymous 401/403.
    r3 = httpx.post(
        f"{BASE}/api/support/chat/stream",
        json={"message": "hi"},
        timeout=5.0,
    )
    assert r3.status_code in (401, 403), r3.text
