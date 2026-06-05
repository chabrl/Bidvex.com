"""
iter283-deposit-btn-fit — Deposit-required CTA must fit the button.

Bug: The "Place Bid" CTA on vehicle + listing detail pages was
stacking EN + FR translations into a single button label
("Security Hold Required — $500 on your card" + "Retenue de
sécurité requise — 500 $ sur votre carte"). Both lines exceeded
the button width at 375px, clipping copy from both edges.

Fix:
  • Single language per render (driven by `i18n.language`).
  • Short headline + amount on a second line.
  • `min-w-0` + `break-words` + `text-center` so future copy can't
    overflow the button bounds.
"""
from __future__ import annotations

import os


def _read_fe(rel: str) -> str:
    base = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src")
    )
    with open(os.path.join(base, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _deposit_block(src: str) -> str:
    idx = src.find('data-testid="bid-btn-deposit-required"')
    assert idx > 0, "deposit CTA testid missing"
    # 1200 chars covers the conditional render block on both files.
    return src[max(0, idx - 600):idx + 1200]


def test_vehicle_deposit_button_single_language():
    """VehicleDetailPage's deposit-required CTA renders ONE language
    at a time — not the stacked EN+FR pair that caused the clip."""
    src = _read_fe("pages/vehicles/VehicleDetailPage.js")
    block = _deposit_block(src)
    # Locale-aware branching present.
    assert "i18n.language?.startsWith('fr')" in block
    # EN headline + FR headline are SEPARATE strings — never glued.
    assert "'Security Hold Required'" in block
    assert "'Retenue de sécurité requise'" in block
    # The stacked-line variant from the legacy code is GONE.
    assert "Security Hold Required — $500 on your card" not in src
    assert "Retenue de sécurité requise — 500 $ sur votre carte" not in src


def test_listing_deposit_button_single_language():
    """Same fix on ListingDetailPage (storage / lots surface)."""
    src = _read_fe("pages/ListingDetailPage.js")
    block = _deposit_block(src)
    assert "i18n.language?.startsWith('fr')" in block
    assert "'Security Hold Required'" in block
    assert "'Retenue de sécurité requise'" in block
    # Legacy concatenated copy removed.
    assert "Security Hold Required — $500 on your card" not in src
    assert "Retenue de sécurité requise — 500 $ sur votre carte" not in src


def test_deposit_button_has_overflow_guards():
    """The container span MUST clamp overflow (`min-w-0` +
    `max-w-full` + `text-center`) so any future translation that
    runs slightly long still fits the button bounds."""
    for path in (
        "pages/vehicles/VehicleDetailPage.js",
        "pages/ListingDetailPage.js",
    ):
        src = _read_fe(path)
        block = _deposit_block(src)
        # Outer flex container has the overflow guards.
        for marker in ("min-w-0", "max-w-full", "text-center"):
            assert marker in block, f"{path}: missing {marker!r} guard"
        # Inner headline uses break-words so long French phrases
        # wrap rather than clip.
        assert "break-words" in block, f"{path}: missing break-words"
        # Shield icon is flex-shrink-0 so it never compresses to nothing.
        assert "flex-shrink-0" in block, (
            f"{path}: Shield icon missing flex-shrink-0 (would squish "
            "to invisible at narrow widths)"
        )


def test_deposit_button_amount_line_shortened():
    """Amount line is `$500 hold on your card` (not the
    `— $500 on your card` em-dash variant which read awkwardly
    and overflowed). FR mirror: `500 $ retenus sur votre carte`."""
    for path in (
        "pages/vehicles/VehicleDetailPage.js",
        "pages/ListingDetailPage.js",
    ):
        src = _read_fe(path)
        block = _deposit_block(src)
        assert "$500 hold on your card" in block
        assert "500 $ retenus sur votre carte" in block
