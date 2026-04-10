"""
BidVex Translation Service — Gemini 2.5 Flash
Provides automated EN<->FR translation for listing content.

Strategy:
- Uses litellm with Emergent proxy (EMERGENT_LLM_KEY) or standard Gemini key (GEMINI_API_KEY)
- Both missing: translation silently skipped (listing saves normally, just not translated)
"""

import os
import logging
import asyncio
import litellm
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Resolve API key: prefer EMERGENT_LLM_KEY, fallback to GEMINI_API_KEY
LLM_KEY = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("GEMINI_API_KEY", "")
_IS_EMERGENT = LLM_KEY.startswith("sk-emergent-") if LLM_KEY else False
_PROXY_URL = os.environ.get("INTEGRATION_PROXY_URL", "https://integrations.emergentagent.com")

if LLM_KEY:
    logger.info(f"[i18n] Translation service initialized (emergent_proxy={_IS_EMERGENT})")
else:
    logger.warning("[i18n] No API key set — translations will be skipped")


async def _translate_via_litellm(text: str, system_prompt: str) -> Optional[str]:
    """Translate using litellm routed through Emergent proxy or direct Gemini."""
    params = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "api_key": LLM_KEY,
        "max_tokens": 2048,
        "temperature": 0.3,
    }
    if _IS_EMERGENT:
        params["model"] = "gemini/gemini-2.5-flash"
        params["api_base"] = _PROXY_URL + "/llm"
        params["custom_llm_provider"] = "openai"
        app_url = os.environ.get("APP_URL") or os.environ.get("REACT_APP_BACKEND_URL", "")
        if app_url:
            params["extra_headers"] = {"X-App-ID": app_url}
    else:
        params["model"] = "gemini/gemini-2.5-flash"

    response = litellm.completion(**params)
    content = response.choices[0].message.content
    return content.strip() if content else None


async def translate_text(text: str, source_lang: str = "en", target_lang: str = "fr") -> Optional[str]:
    """
    Translate text between EN and FR using Gemini 2.5 Flash.
    Returns translated text or None on failure.
    """
    if not text or not text.strip():
        return text
    if not LLM_KEY:
        logger.warning("[i18n] No API key set — skipping translation")
        return None

    lang_names = {"en": "English", "fr": "French"}
    src = lang_names.get(source_lang, "English")
    tgt = lang_names.get(target_lang, "French")

    system_prompt = (
        f"You are a professional translator specializing in Quebec French (Canadian French). "
        f"Translate the following {src} text to {tgt}. "
        f"Preserve all formatting, line breaks, and HTML tags. "
        f"Use natural Quebec French conventions (e.g., 'enchères' not 'ventes aux enchères'). "
        f"Return ONLY the translated text with no explanations or preamble."
    )

    try:
        translated = await _translate_via_litellm(text, system_prompt)

        if translated:
            logger.info(f"[i18n] Translated ({source_lang}->{target_lang}): '{text[:50]}...' -> '{translated[:50]}...'")
        return translated

    except Exception as e:
        logger.error(f"[i18n] Translation failed ({source_lang}->{target_lang}): {e}")
        return None


async def translate_listing_fields(
    title: str,
    description: str,
    source_lang: str = "en",
) -> Dict[str, Optional[str]]:
    """
    Translate title and description concurrently.
    Returns dict with translated fields.
    """
    target_lang = "fr" if source_lang == "en" else "en"

    title_task = translate_text(title, source_lang, target_lang)
    desc_task = translate_text(description, source_lang, target_lang)

    title_translated, desc_translated = await asyncio.gather(title_task, desc_task)

    return {
        f"title_{source_lang}": title,
        f"title_{target_lang}": title_translated or title,
        f"description_{source_lang}": description,
        f"description_{target_lang}": desc_translated or description,
    }


async def translate_lot_fields(
    lots: list,
    source_lang: str = "en",
) -> list:
    """
    Translate lot titles and descriptions concurrently.
    Returns updated lots with _en/_fr fields.
    """
    target_lang = "fr" if source_lang == "en" else "en"

    async def translate_single_lot(lot: dict) -> dict:
        title = lot.get("title", "")
        description = lot.get("description", "")

        title_t, desc_t = await asyncio.gather(
            translate_text(title, source_lang, target_lang),
            translate_text(description, source_lang, target_lang),
        )

        lot[f"title_{source_lang}"] = title
        lot[f"title_{target_lang}"] = title_t or title
        lot[f"description_{source_lang}"] = description
        lot[f"description_{target_lang}"] = desc_t or description
        return lot

    tasks = [translate_single_lot(lot) for lot in lots]
    return await asyncio.gather(*tasks)


async def backfill_listing_translations(db) -> Dict[str, int]:
    """
    Backfill translations for existing listings that lack _en/_fr fields.
    Returns count of translated documents.
    """
    stats = {"single": 0, "multi": 0, "lots": 0, "errors": 0}

    # Single listings without title_en
    cursor = db.listings.find(
        {"title_en": {"$exists": False}, "status": "active"},
        {"_id": 0, "id": 1, "title": 1, "description": 1}
    )
    async for doc in cursor:
        try:
            fields = await translate_listing_fields(doc["title"], doc.get("description", ""), "en")
            await db.listings.update_one(
                {"id": doc["id"]},
                {"$set": fields}
            )
            stats["single"] += 1
        except Exception as e:
            logger.error(f"Backfill failed for listing {doc['id']}: {e}")
            stats["errors"] += 1

    # Multi-item listings without title_en
    cursor = db.multi_item_listings.find(
        {"title_en": {"$exists": False}, "status": {"$in": ["active", "upcoming"]}},
        {"_id": 0, "id": 1, "title": 1, "description": 1, "lots": 1}
    )
    async for doc in cursor:
        try:
            fields = await translate_listing_fields(doc["title"], doc.get("description", ""), "en")

            # Translate lots
            lots = doc.get("lots", [])
            if lots:
                translated_lots = await translate_lot_fields(lots, "en")
                # Build $set for each lot's new fields
                lot_updates = {}
                for i, lot in enumerate(translated_lots):
                    for key in ["title_en", "title_fr", "description_en", "description_fr"]:
                        if key in lot:
                            lot_updates[f"lots.{i}.{key}"] = lot[key]
                fields.update(lot_updates)
                stats["lots"] += len(lots)

            await db.multi_item_listings.update_one(
                {"id": doc["id"]},
                {"$set": fields}
            )
            stats["multi"] += 1
        except Exception as e:
            logger.error(f"Backfill failed for multi-listing {doc['id']}: {e}")
            stats["errors"] += 1

    logger.info(f"[i18n] Backfill complete: {stats}")
    return stats
