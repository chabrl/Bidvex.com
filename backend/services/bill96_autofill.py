"""
iter310 — Quebec Bill 96 auto-translation autofill
==================================================

When a Quebec listing is submitted with an English title/description but
NO French copy, this helper transparently translates the English content
into Quebec French via the existing `translation_service` (Gemini 2.5
Flash through the Emergent LLM key) and writes the result back into the
payload BEFORE the hard `assert_qc_bilingual_titles` gate runs.

Goal: turn the Bill 96 hard-block popup (HTTP 422 with
`qc_french_description_required`) into a transparent server-side fill
that lets the listing return 201 Created on the first try, while still
keeping the validator as the floor for genuinely empty submissions.

Caller pattern
--------------
    from services.bill96_autofill import autofill_qc_french_copy

    await autofill_qc_french_copy(listing_data)  # mutates the model
    assert_qc_bilingual_titles(...)              # now a no-op for normal flow

Returns a dict describing what was filled (or skipped/failed) so the
caller can surface a `translation_applied` flag in the response — the
frontend uses that to show a "Translated for Bill 96 compliance" badge
on the success toast.
"""
from __future__ import annotations

import logging
from typing import Any, Optional


logger = logging.getLogger(__name__)


# Quebec detection mirrors `qc_bilingual_validator._is_quebec_listing`
# so the autofill triggers on exactly the same set of listings the
# validator would reject — never more, never less.
def _is_quebec_listing(region: Optional[str], city: Optional[str]) -> bool:
    r = (region or "").strip().upper()
    if r in ("QC", "QUEBEC"):
        return True
    if not r:
        c = (city or "").strip().lower()
        if c in (
            "montreal", "montréal", "quebec", "québec", "sherbrooke",
            "laval", "gatineau", "longueuil", "saguenay",
            "trois-rivieres", "trois-rivières", "levis", "lévis",
        ):
            return True
    return False


def _is_blank(v: Optional[str]) -> bool:
    return v is None or not str(v).strip()


def _get(obj: Any, key: str) -> Any:
    """Read `key` from a Pydantic model OR plain dict."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _set(obj: Any, key: str, value: Any) -> None:
    """Write `key` on a Pydantic model OR plain dict."""
    if isinstance(obj, dict):
        obj[key] = value
        return
    try:
        setattr(obj, key, value)
    except Exception:  # noqa: BLE001 — pydantic v2 sometimes blocks setattr
        # Fall back via model_copy for frozen models — rare in this codebase
        logger.warning(f"[bill96-autofill] setattr({key}) failed; skipping")


async def autofill_qc_french_copy(
    listing_data: Any,
    *,
    region_override: Optional[str] = None,
    city_override: Optional[str] = None,
) -> dict:
    """If the listing is in Quebec and missing French copy, fill it
    in via the translation service. Mutates `listing_data` in place.

    `region_override` / `city_override` are for callers whose payload
    field is named differently (e.g. `vehicles.py` uses `province`
    rather than `region`).

    Returns:
        {
          "applied": bool,                # True iff anything was filled
          "fields": list[str],            # which fields were filled
          "skipped": str | None,          # "not_quebec" / "no_source" / "already_filled" / "translator_unavailable"
        }
    """
    region = region_override if region_override is not None else _get(listing_data, "region")
    city = city_override if city_override is not None else _get(listing_data, "city")
    if not _is_quebec_listing(region, city):
        return {"applied": False, "fields": [], "skipped": "not_quebec"}

    title = _get(listing_data, "title")
    title_fr = _get(listing_data, "title_fr")
    description = _get(listing_data, "description")
    description_fr = _get(listing_data, "description_fr")

    needs_title = (not _is_blank(title)) and _is_blank(title_fr)
    needs_desc = (not _is_blank(description)) and _is_blank(description_fr)

    if not (needs_title or needs_desc):
        return {"applied": False, "fields": [], "skipped": "already_filled"}

    # Lazy import — keeps the dependency optional and avoids circular
    # import with the listings service.
    try:
        from services.translation_service import translate_text
    except Exception as exc:  # pragma: no cover
        logger.error(f"[bill96-autofill] translator import failed: {exc}")
        return {"applied": False, "fields": [], "skipped": "translator_unavailable"}

    filled: list[str] = []

    if needs_title:
        translated = await translate_text(title, source_lang="en", target_lang="fr")
        if translated and translated.strip():
            _set(listing_data, "title_fr", translated.strip())
            filled.append("title_fr")
        else:
            logger.warning("[bill96-autofill] title translation returned empty")

    if needs_desc:
        translated = await translate_text(description, source_lang="en", target_lang="fr")
        if translated and translated.strip():
            _set(listing_data, "description_fr", translated.strip())
            filled.append("description_fr")
        else:
            logger.warning("[bill96-autofill] description translation returned empty")

    if not filled:
        return {"applied": False, "fields": [], "skipped": "translator_unavailable"}

    logger.info(f"[bill96-autofill] auto-translated {filled} for QC listing")
    return {"applied": True, "fields": filled, "skipped": None}
