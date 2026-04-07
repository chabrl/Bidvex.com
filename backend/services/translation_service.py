"""
BidVex Translation Service — Gemini 2.5 Flash via Emergent LLM Key
Provides automated EN<->FR translation for listing content.
"""

import os
import logging
import asyncio
from typing import Optional, Dict
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env", override=False)

logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")


async def translate_text(text: str, source_lang: str = "en", target_lang: str = "fr") -> Optional[str]:
    """
    Translate text between EN and FR using Gemini 2.5 Flash.
    Returns translated text or None on failure.
    """
    if not text or not text.strip():
        return text
    if not EMERGENT_LLM_KEY:
        logger.warning("EMERGENT_LLM_KEY not set — skipping translation")
        return None

    lang_names = {"en": "English", "fr": "French"}
    src = lang_names.get(source_lang, "English")
    tgt = lang_names.get(target_lang, "French")

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"translate-{id(text)}",
            system_message=(
                f"You are a professional translator specializing in Quebec French (Canadian French). "
                f"Translate the following {src} text to {tgt}. "
                f"Preserve all formatting, line breaks, and HTML tags. "
                f"Use natural Quebec French conventions (e.g., 'enchères' not 'ventes aux enchères'). "
                f"Return ONLY the translated text with no explanations or preamble."
            ),
        )
        chat.with_model("gemini", "gemini-2.5-flash")

        user_message = UserMessage(text=text)
        response = await chat.send_message(user_message)
        translated = response.strip() if response else None
        if translated:
            logger.info(f"Translated ({source_lang}->{target_lang}): '{text[:50]}...' -> '{translated[:50]}...'")
        return translated

    except Exception as e:
        logger.error(f"Translation failed ({source_lang}->{target_lang}): {e}")
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

    logger.info(f"Backfill complete: {stats}")
    return stats
