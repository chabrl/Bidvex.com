"""
iter310 — Quebec Bill 96 auto-translation autofill (Directive 2)
=================================================================

Scope
-----
1. Backend autofill helper (`services.bill96_autofill.autofill_qc_french_copy`):
   • Quebec QC listings with EN title/description but blank `*_fr` are
     auto-translated via Gemini 2.5 Flash and the FR fields populated
     in-place BEFORE the hard `assert_qc_bilingual_titles` validator
     runs.
   • Non-Quebec listings are skipped.
   • Already-filled FR fields are untouched.
2. Listing/Vehicle/Storage routes wire the autofill in.
3. Frontend (CreateListingPage.js / CreateMultiItemListing.js) replaces
   the hard-block popup with a "Translating…" loading toast in both
   EN and FR (smoke-checked by reading the source).

These tests are CI-safe: the translator is mocked at the call site so
no live LLM call is required. A separate "live trace" sanity check
hits the real translation endpoint only when `EMERGENT_LLM_KEY` is set
in the environment.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest

pytestmark = pytest.mark.monetization


# ─── Source-integrity assertions ─────────────────────────────────────


def test_bill96_autofill_service_exists():
    """The new autofill module must exist and export the public helper."""
    path = Path("/app/backend/services/bill96_autofill.py")
    assert path.is_file()
    src = path.read_text()
    assert "async def autofill_qc_french_copy" in src
    assert "_is_quebec_listing" in src
    # Wired to the existing translation service
    assert "from services.translation_service import translate_text" in src
    # Returns the directive's expected dict shape
    assert '"applied"' in src and '"fields"' in src and '"skipped"' in src


def test_listings_route_calls_autofill_before_validator():
    """The single-listing POST must autofill BEFORE the hard validator."""
    src = Path("/app/backend/routes/listings.py").read_text()
    # Both call sites (single listing + multi-item listing) must wire the
    # autofill helper.
    assert src.count("autofill_qc_french_copy") >= 2
    # In single listing flow, autofill must run before assert_qc_bilingual.
    pos_autofill = src.find("autofill_qc_french_copy(listing_data)")
    pos_validator = src.find("assert_qc_bilingual_titles(", pos_autofill)
    assert pos_autofill > 0, "autofill call site not found in single listing flow"
    assert pos_validator > 0, "validator call not found AFTER autofill"
    assert pos_autofill < pos_validator, "autofill must precede validator"


def test_vehicle_route_calls_autofill_with_region_override():
    """Vehicle payloads name the field `province` (not `region`) — the
    autofill helper accepts a `region_override` to bridge that."""
    src = Path("/app/backend/routes/vehicles.py").read_text()
    assert "from services.bill96_autofill import autofill_qc_french_copy" in src
    assert "region_override" in src


def test_storage_route_calls_translation_helper():
    """Storage auctions use `description_en`/`description_fr` (no
    title field). The route calls `translate_text` directly to fill
    `description_fr` before the validator."""
    src = Path("/app/backend/routes/storage_auctions.py").read_text()
    assert "from services.translation_service import translate_text" in src
    assert "iter310" in src, "iter310 marker comment must remain"


def test_frontend_listing_page_uses_loading_toast_instead_of_block():
    src = Path("/app/frontend/src/pages/CreateListingPage.js").read_text()
    # The hard-block call to validateFrenchTitle in handleSubmit MUST be
    # replaced (the function itself can remain in bill96.js for legacy
    # callers but the create-listing page no longer hard-blocks).
    # We check via the new EN + FR messages introduced in iter310:
    assert "Translating and formatting listing for Bill 96 compliance" in src
    assert "Traduction et mise en conformité avec la Loi 96" in src
    assert "toast.loading(" in src
    assert "bill96-translating" in src
    # The legacy hard-block (with toast.error + scrollIntoView + return)
    # must be gone from handleSubmit.
    assert (
        "validateFrenchTitle({ isQuebec, titleFr: formData.title_fr })" not in src
    ), "CreateListingPage.js still hard-blocks instead of soft-translating"


def test_frontend_multi_item_page_uses_loading_toast():
    src = Path("/app/frontend/src/pages/CreateMultiItemListing.js").read_text()
    assert "Translating and formatting listing for Bill 96 compliance" in src
    assert "Traduction et mise en conformité avec la Loi 96" in src
    assert "bill96-translating-multi" in src
    assert (
        "validateFrenchTitle({ isQuebec, titleFr: formData.title_fr })" not in src
    ), "CreateMultiItemListing.js still hard-blocks instead of soft-translating"


# ─── Unit tests on the autofill helper ───────────────────────────────


@pytest.mark.asyncio
async def test_autofill_skips_non_quebec_listings():
    """Outside-of-Quebec submissions must never hit the translator."""
    from services.bill96_autofill import autofill_qc_french_copy

    payload = type("Obj", (), {})()
    payload.title = "Antique Camera"
    payload.title_fr = None
    payload.description = "Vintage lens"
    payload.description_fr = None
    payload.region = "ON"
    payload.city = "Toronto"

    with patch(
        "services.translation_service.translate_text",
        new=AsyncMock(return_value="should not be called"),
    ) as mocked:
        result = await autofill_qc_french_copy(payload)
        assert mocked.await_count == 0

    assert result == {"applied": False, "fields": [], "skipped": "not_quebec"}
    assert payload.title_fr is None
    assert payload.description_fr is None


@pytest.mark.asyncio
async def test_autofill_already_filled_listings_are_a_no_op():
    """Don't waste an LLM call if the seller provided the French copy."""
    from services.bill96_autofill import autofill_qc_french_copy

    payload = type("Obj", (), {})()
    payload.title = "Antique Lamp"
    payload.title_fr = "Lampe ancienne"
    payload.description = "An antique brass lamp."
    payload.description_fr = "Une lampe en laiton ancienne."
    payload.region = "QC"
    payload.city = "Montreal"

    with patch(
        "services.translation_service.translate_text",
        new=AsyncMock(return_value="should not be called"),
    ) as mocked:
        result = await autofill_qc_french_copy(payload)
        assert mocked.await_count == 0

    assert result["applied"] is False
    assert result["skipped"] == "already_filled"


@pytest.mark.asyncio
async def test_autofill_fills_missing_french_for_quebec_qc_region():
    """QC + missing description_fr → translator is called and result
    is written back to the payload."""
    from services.bill96_autofill import autofill_qc_french_copy

    payload = type("Obj", (), {})()
    payload.title = "Bike"
    payload.title_fr = None
    payload.description = "A mountain bike, mint condition."
    payload.description_fr = None
    payload.region = "QC"
    payload.city = "Montréal"

    fake = AsyncMock(side_effect=[
        "Vélo",  # first call: title
        "Un vélo de montagne, état impeccable.",  # second call: description
    ])
    with patch("services.translation_service.translate_text", new=fake):
        result = await autofill_qc_french_copy(payload)

    assert result["applied"] is True
    assert sorted(result["fields"]) == ["description_fr", "title_fr"]
    assert payload.title_fr == "Vélo"
    assert payload.description_fr == "Un vélo de montagne, état impeccable."


@pytest.mark.asyncio
async def test_autofill_quebec_detected_by_city_when_region_blank():
    """Montréal city alone should trigger the autofill (region blank)."""
    from services.bill96_autofill import autofill_qc_french_copy

    payload = type("Obj", (), {})()
    payload.title = "Outboard motor"
    payload.title_fr = None
    payload.description = None
    payload.description_fr = None
    payload.region = ""
    payload.city = "Sherbrooke"

    fake = AsyncMock(return_value="Moteur hors-bord")
    with patch("services.translation_service.translate_text", new=fake):
        result = await autofill_qc_french_copy(payload)

    assert result["applied"] is True
    assert "title_fr" in result["fields"]
    assert payload.title_fr == "Moteur hors-bord"


@pytest.mark.asyncio
async def test_autofill_region_override_for_vehicle_payloads():
    """Vehicle payloads use `province`, not `region`. The
    region_override kwarg must bridge that."""
    from services.bill96_autofill import autofill_qc_french_copy

    payload = type("Obj", (), {})()
    payload.title = "2018 Honda Civic"
    payload.title_fr = None
    payload.description = "Clean title, 80k km."
    payload.description_fr = None
    # No `region` attribute at all; vehicle code passes `province` via
    # region_override.
    payload.province = "QC"
    payload.city = "Quebec City"

    fake = AsyncMock(side_effect=["Honda Civic 2018", "Titre propre, 80 000 km."])
    with patch("services.translation_service.translate_text", new=fake):
        result = await autofill_qc_french_copy(payload, region_override="QC")

    assert result["applied"] is True
    assert payload.title_fr == "Honda Civic 2018"
    assert payload.description_fr == "Titre propre, 80 000 km."


@pytest.mark.asyncio
async def test_autofill_translator_failure_returns_unavailable_status():
    """If the translator returns None (LLM down), the helper must not
    silently claim success — it returns skipped='translator_unavailable'."""
    from services.bill96_autofill import autofill_qc_french_copy

    payload = type("Obj", (), {})()
    payload.title = "Hammer"
    payload.title_fr = None
    payload.description = None
    payload.description_fr = None
    payload.region = "QC"
    payload.city = "Quebec"

    fake = AsyncMock(return_value=None)
    with patch("services.translation_service.translate_text", new=fake):
        result = await autofill_qc_french_copy(payload)

    assert result["applied"] is False
    assert result["skipped"] == "translator_unavailable"
    assert payload.title_fr is None


@pytest.mark.asyncio
async def test_autofill_accepts_dict_payload():
    """Some upstream code passes plain dicts — helper must mutate
    those too."""
    from services.bill96_autofill import autofill_qc_french_copy

    payload = {
        "title": "Painting",
        "title_fr": None,
        "description": None,
        "description_fr": None,
        "region": "QC",
        "city": "Montreal",
    }

    with patch(
        "services.translation_service.translate_text",
        new=AsyncMock(return_value="Tableau"),
    ):
        result = await autofill_qc_french_copy(payload)

    assert result["applied"] is True
    assert payload["title_fr"] == "Tableau"


# ─── End-to-end translator wiring (skipped without LLM key) ───────────


@pytest.mark.skipif(
    not os.environ.get("EMERGENT_LLM_KEY"),
    reason="No EMERGENT_LLM_KEY — live translation skipped in CI",
)
@pytest.mark.asyncio
async def test_live_translation_returns_french_text():
    """One real round-trip through the translator to prove the autofill
    works end-to-end when the LLM key is wired. Skipped in CI envs
    without a key (so this test never blocks the gate)."""
    from services.translation_service import translate_text
    out = await translate_text("Antique table lamp", source_lang="en", target_lang="fr")
    assert out and isinstance(out, str)
    assert len(out.strip()) >= 3
    # The translation should differ from the English source (the LLM
    # never returns the exact input verbatim for a known-translatable
    # noun phrase). We deliberately don't assert exact phrasing — Gemini
    # is non-deterministic at temperature 0.3, and short noun phrases
    # like "Antique table lamp" may translate to phrasings without
    # accented characters (e.g. "Lampe de table ancienne").
    assert out.strip().lower() != "antique table lamp", \
        f"translator returned input verbatim: {out!r}"
