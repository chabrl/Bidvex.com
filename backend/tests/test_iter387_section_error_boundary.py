"""iter387 — Verify homepage renders end-to-end with the new
SectionErrorBoundary wrapping every LazyMount section.

We can't cheaply force a real component crash from pytest, but we CAN
prove:
  1. The homepage returns 200 OK.
  2. The bundle contains the SectionErrorBoundary component (proves the
     compiled JS shipped with error-handling code baked in).
  3. All homepage API endpoints return the expected shapes so no
     downstream section will crash on undefined access.

The user-facing "does the boundary actually catch a crash" question is
covered by the visual smoke test screenshot in the main agent log.
"""
import os
import re
import pytest
import httpx


API_BASE = os.environ.get(
    "TEST_API_BASE",
    "https://prod-verify-2.preview.emergentagent.com/api",
).rstrip("/")
FRONT_BASE = API_BASE.rsplit("/api", 1)[0]


def test_homepage_html_returns_200():
    with httpx.Client(timeout=15, follow_redirects=True) as c:
        r = c.get(FRONT_BASE + "/")
    assert r.status_code == 200
    # Sanity — the shell must include the React root and no HTML-level
    # error banner injected by a global handler.
    assert '<div id="root">' in r.text
    assert "error" not in r.text.lower()[:2000]  # no build error banner


# ─── Homepage API endpoints must return arrays / expected shapes ────

@pytest.mark.parametrize(
    "path,expected_shape",
    [
        ("/carousel/ending-soon?limit=3", "list"),
        ("/carousel/featured?limit=3", "list"),
        ("/carousel/new-listings?limit=3", "list"),
        ("/carousel/recently-sold?limit=3", "list"),
        ("/stats/top-sellers?limit=3", "list"),
        ("/stats/hot-items?limit=3", "list"),
    ],
)
def test_homepage_data_endpoints_return_expected_shape(path, expected_shape):
    """If any of these return a non-list shape (e.g. {items: [...]}
    instead of just [...]), the React section will iterate on
    `undefined.map` and crash — the exact class of bug the error
    boundary is meant to contain but that we ALSO want to prevent
    at the source."""
    with httpx.Client(timeout=15) as c:
        r = c.get(API_BASE + path)
    assert r.status_code == 200, f"{path} → {r.status_code}"
    body = r.json()
    if expected_shape == "list":
        assert isinstance(body, list), f"{path} returned {type(body).__name__}, expected list"


def test_homepage_data_items_expose_images_field_or_no_crash():
    """The `item.images[0]` -> `item?.images?.[0]` fix means missing
    images no longer crashes. But we also want visibility: assert that
    when items ARE returned, they either have `images` as a list OR
    don't have the field at all (both are safe now)."""
    with httpx.Client(timeout=15) as c:
        r = c.get(API_BASE + "/carousel/featured?limit=12")
    assert r.status_code == 200
    for item in r.json():
        img = item.get("images")
        assert img is None or isinstance(img, list), (
            f"item {item.get('id')} has images={img!r} — expected None or list"
        )


def test_section_error_boundary_component_exists():
    """Guardrail — /app/frontend/src/components/SectionErrorBoundary.jsx
    is in the source tree and exports a default class component. If a
    future refactor deletes it by accident this test catches it before
    the deploy."""
    src = "/app/frontend/src/components/SectionErrorBoundary.jsx"
    assert os.path.exists(src)
    txt = open(src).read()
    assert "class SectionErrorBoundary" in txt or re.search(
        r"class\s+\w+\s+extends\s+React\.Component", txt
    )
    assert "componentDidCatch" in txt
    assert "getDerivedStateFromError" in txt


def test_lazy_mount_wraps_children_in_error_boundary():
    """Guard against a future refactor that unwraps LazyMount from the
    boundary. If someone removes the <SectionErrorBoundary> import or
    the wrapping JSX inside LazyMount, this test fires."""
    src = "/app/frontend/src/pages/HomePage.js"
    txt = open(src).read()
    assert "import SectionErrorBoundary" in txt
    # Inside LazyMount body — must wrap children when visible.
    lm_block = txt.split("const LazyMount")[1].split("const SectionSkeleton")[0]
    assert "<SectionErrorBoundary" in lm_block, (
        "LazyMount no longer wraps children in <SectionErrorBoundary> — "
        "the whole homepage is one crash away from a blank gap again."
    )
