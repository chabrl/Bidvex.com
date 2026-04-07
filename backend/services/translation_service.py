"""
BidVex Translation Service — Gemini 2.5 Flash
Provides automated EN<->FR translation for listing content.

Strategy:
- Preview environment: uses emergentintegrations + EMERGENT_LLM_KEY (if available)
- Railway production: uses google-generativeai + GEMINI_API_KEY
- Both missing: translation silently skipped (listing saves normally, just not translated)
"""

import os
import logging
import asyncio
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Resolve API key: prefer GEMINI_API_KEY (production), fallback to EMERGENT_LLM_KEY (preview)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")

# Detect which SDK is available
_USE_EMERGENT = False
_USE_GOOGLE = False

try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    _USE_EMERGENT = True
    logger.info("[i18n] Using emergentintegrations SDK for translations")
except ImportError:
    pass

if not _USE_EMERGENT:
    try:
        import google.generativeai as genai
        _USE_GOOGLE = True
        logger.info("[i18n] Using google-generativeai SDK for translations")
    except ImportError:
        logger.warning("[i18n] No translation SDK available — translations will be skipped")


async def _translate_via_emergent(text: str, system_prompt: str) -> Optional[str]:
    """Translate using emergentintegrations (Emergent preview environment)."""
    chat = LlmChat(
        api_key=GEMINI_API_KEY,
        session_id=f"translate-{id(text)}",
        system_message=system_prompt,
    )
    chat.with_model("gemini", "gemini-2.5-flash")
    response = await chat.send_message(UserMessage(text=text))
    return response.strip() if response else None


async def _translate_via_google(text: str, system_prompt: str) -> Optional[str]:
    """Translate using standard google-generativeai SDK (Railway production)."""
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_prompt,
    )
    response = await asyncio.to_thread(
        model.generate_content, text
    )
    return response.text.strip() if response and response.text else None


async def translate_text(text: str, source_lang: str = "en", target_lang: str = "fr") -> Optional[str]:
    """
    Translate text between EN and FR using Gemini 2.5 Flash.
    Returns translated text or None on failure.
    """
    if not text or not text.strip():
        return text
    if not GEMINI_API_KEY:
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
        if _USE_EMERGENT:
            translated = await _translate_via_emergent(text, system_prompt)
        elif _USE_GOOGLE:
            translated = await _translate_via_google(text, system_prompt)
        else:
            return None

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
