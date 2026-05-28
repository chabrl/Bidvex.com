"""
BidVex Master Concierge AI Assistant v2
RAG-based luxury auction specialist powered by Gemini 2.5 Flash
"""

import os
import json
import logging
import uuid
import litellm
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Knowledge base import (graceful if unavailable)
try:
    from services.ai_knowledge_base_v2 import get_knowledge_base
except Exception:
    get_knowledge_base = None

# iter235 — Single canonical system instruction shared with the direct
# google-genai path. Importing it (rather than duplicating) guarantees
# both /api/ai-chat/message (this file) and /api/chat/stream
# (services/genai_direct_client.py) speak with the same identity, anti-
# hallucination guardrails, and broker rules.
from services.genai_direct_client import WATCHDOG_SYSTEM_INSTRUCTION


class BidVexAssistant:
    """BidVex AI Core — litellm path (parity with /api/chat/stream)."""

    SYSTEM_INSTRUCTIONS = WATCHDOG_SYSTEM_INSTRUCTION

    def __init__(self, api_key: str, db):
        """Initialize the AI Assistant with Gemini 2.5 Flash via Emergent LLM Proxy (with direct-Gemini fallback)"""
        self.api_key = api_key
        self.db = db
        self.model_name = os.environ.get("AI_MODEL_ID", "gemini-2.5-flash")
        self.is_emergent_key = api_key.startswith("sk-emergent-") if api_key else False
        self.proxy_url = os.environ.get("INTEGRATION_PROXY_URL", "https://integrations.emergentagent.com")
        # Native Gemini key fallback — used if Emergent proxy fails (Railway / prod network issues)
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
        logger.info(
            f"BidVex Master Concierge initialized with {self.model_name} "
            f"(emergent_proxy={self.is_emergent_key}, gemini_fallback={'yes' if self.gemini_api_key else 'no'})"
        )

        # Initialize knowledge base
        try:
            self.kb = get_knowledge_base() if get_knowledge_base else None
        except Exception as e:
            logger.error(f"Error initializing knowledge base: {e}")
            self.kb = None

    async def _call_llm(self, messages: list) -> str:
        """
        Call the LLM with a Emergent-proxy-first, native-Gemini-fallback strategy.
        iter211 — Each provider gets ONE retry with 800ms backoff before falling
        through to the next provider, since the most common production failure
        is a transient Gemini rate-limit or 5xx that succeeds on a second try.
        Returns the response text. Raises on total failure.
        """
        import asyncio

        async def _attempt(params: dict, *, label: str, retries: int = 1):
            """Try once, retry on transient error."""
            last_err = None
            for attempt in range(retries + 1):
                try:
                    response = await litellm.acompletion(**params)
                    return response.choices[0].message.content
                except Exception as e:  # noqa: BLE001
                    last_err = e
                    classification = type(e).__name__
                    is_transient = any(s in str(e).lower() for s in (
                        "timeout", "rate limit", "rate_limit", "429",
                        "503", "502", "504", "overloaded", "internal error",
                    ))
                    if attempt < retries and is_transient:
                        backoff = 0.8 * (2 ** attempt)
                        logger.warning(
                            f"[AI_CONCIERGE] {label} attempt {attempt + 1} transient {classification} ({e}); "
                            f"retrying in {backoff:.1f}s"
                        )
                        await asyncio.sleep(backoff)
                        continue
                    raise
            raise last_err  # type: ignore

        # Attempt 1: Emergent proxy (preferred — free via EMERGENT_LLM_KEY)
        if self.is_emergent_key and self.api_key:
            try:
                params = {
                    "model": f"gemini/{self.model_name}",
                    "messages": messages,
                    "api_key": self.api_key,
                    "api_base": self.proxy_url + "/llm",
                    "custom_llm_provider": "openai",
                    "max_tokens": 768,
                    "temperature": 0.7,
                    "timeout": 25,
                }
                app_url = os.environ.get("APP_URL") or os.environ.get("REACT_APP_BACKEND_URL", "")
                if app_url:
                    params["extra_headers"] = {"X-App-ID": app_url}
                return await _attempt(params, label="Emergent proxy")
            except Exception as e:
                # Log loud enough that Railway shows it
                logger.error(f"[AI_CONCIERGE] Emergent proxy failed after retry: {type(e).__name__}: {e}. Falling back to direct Gemini API…")

        # Attempt 2: Native Gemini API (fallback — requires GEMINI_API_KEY)
        if self.gemini_api_key:
            try:
                return await _attempt(
                    {
                        "model": f"gemini/{self.model_name}",
                        "messages": messages,
                        "api_key": self.gemini_api_key,
                        "max_tokens": 768,
                        "temperature": 0.7,
                        "timeout": 25,
                    },
                    label="Direct Gemini",
                )
            except Exception as e:
                logger.error(f"[AI_CONCIERGE] Direct Gemini API failed after retry: {type(e).__name__}: {e}")
                raise

        # No keys available
        raise RuntimeError(
            "No LLM credentials available — set EMERGENT_LLM_KEY or GEMINI_API_KEY in environment."
        )

    async def chat(self, user_message: str, user_id: Optional[str] = None,
                   chat_history: List[Dict] = None, language: str = "en",
                   lot_id: Optional[str] = None, listing_id: Optional[str] = None) -> Dict[str, Any]:
        """Process user message and generate response"""
        try:
            # Detect language
            if not language or language not in ['en', 'fr']:
                language = self._detect_language(user_message)

            # Search knowledge base for relevant context
            context = ""
            if self.kb:
                try:
                    kb_results = self.kb.search(user_message, n_results=3)
                    context = self._format_knowledge_context(kb_results)
                except Exception:
                    pass

            # Fetch lot-specific seller obligations
            lot_context = ""
            if listing_id:
                lot_context = await self._get_lot_obligations_context(listing_id, lot_id)

            # Combine contexts
            if lot_context:
                context = f"{lot_context}\n\n{context}" if context else lot_context

            # Build enhanced message
            enhanced_message = user_message
            if context:
                enhanced_message = f"""**Retrieved Knowledge Base Context:**
{context}

**User Question:** {user_message}

Please answer the user's question using the context provided above. If the context doesn't contain relevant information, use your general knowledge about auction platforms."""

            # Build messages array for litellm
            messages = [{"role": "system", "content": self.SYSTEM_INSTRUCTIONS}]

            # Add chat history for multi-turn context
            if chat_history:
                for msg in chat_history[-10:]:
                    role = "user" if msg.get("role") == "user" else "assistant"
                    messages.append({"role": role, "content": msg.get("content", "")})

            # Add current user message
            messages.append({"role": "user", "content": enhanced_message})

            # Call LLM with Emergent-proxy-first, Gemini-fallback strategy.
            # This prevents production outages when the Emergent proxy is unreachable (Railway).
            response_text = await self._call_llm(messages)

            # Check if user needs verification
            needs_verification = False
            if user_id and any(kw in user_message.lower() for kw in ["bid", "sell", "create listing", "enchérir", "vendre"]):
                user_doc = await self.db.users.find_one({"id": user_id})
                if user_doc and user_doc.get("role") != "admin":
                    phone_verified = user_doc.get("phone_verified", False)
                    has_payment = user_doc.get("has_payment_method", False)
                    needs_verification = not (phone_verified and has_payment)

            # Parse response for rich content
            response_data = self._parse_response(response_text, language, needs_verification)

            return {
                "success": True,
                "message": response_text,
                "language": language,
                "rich_content": response_data,
                "needs_verification": needs_verification
            }

        except Exception as e:
            logger.error(f"Error in AI chat: {e}", exc_info=True)
            return {
                "success": False,
                "message": "I apologize, but I'm experiencing technical difficulties. Please try again or contact support@bidvex.com." if language == "en" else "Je m'excuse, mais je rencontre des difficultes techniques. Veuillez reessayer ou contacter support@bidvex.com.",
                "error": str(e),
                "language": language
            }

    def _detect_language(self, text: str) -> str:
        """Detect language (English or French) from text"""
        french_keywords = ['bonjour', 'merci', 'oui', 'non', 'comment', 'pourquoi', 'enchere', 'livraison', 'je', 'vous', 'mon', 'ma', 'est-ce', 'combien', 'quand']
        text_lower = text.lower()
        french_count = sum(1 for keyword in french_keywords if keyword in text_lower)
        return 'fr' if french_count >= 2 else 'en'

    def _format_knowledge_context(self, results: List[Dict]) -> str:
        """Format knowledge base results into context string"""
        if not results:
            return ""
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(f"\n[Context {i} - {result['metadata'].get('section', 'General')}]")
            context_parts.append(result['content'][:800])
        return "\n".join(context_parts)

    async def _get_lot_obligations_context(self, listing_id: str, lot_number: Optional[str] = None) -> str:
        """Fetch and format seller obligations from a specific listing for RAG context.

        iter222 — Now safely falls back across all 3 auction collections:
          1. `multi_item_listings` (sub-lots, lot-level obligations)
          2. `listings` (single-item retail + storage_locker)
          3. `storage_auctions` (dedicated facility-flow storage)
        For storage-locker entries (which intentionally lack `condition`,
        `quantity`, etc.) the helper injects `visible_content_tags` so the
        Gemini concierge can answer "what's inside?" questions without
        falling back to "I don't have that information."
        Returns "" if no listing matches — never raises.
        """
        try:
            return await self._build_safe_listing_context(listing_id, lot_number)
        except Exception as e:  # defensive: NEVER let context-build crash chat
            logger.warning(f"[ai_assistant] context build failed for {listing_id}: {e}")
            return ""

    async def _build_safe_listing_context(self, listing_id: str, lot_number: Optional[str] = None) -> str:
        """Internal — assemble lot context across multiple collections."""
        # 1) Try multi-item first (richest obligations data)
        listing = await self.db.multi_item_listings.find_one({"id": listing_id})
        if listing:
            obligations = listing.get("seller_obligations", {})
            if obligations:
                return self._format_multi_item_obligations(listing, obligations)
            # Multi-item without obligations: render a minimal context
            return self._format_minimal_listing(listing, kind="multi_lot")

        # 2) Try general listings (covers storage_locker)
        listing = await self.db.listings.find_one({"id": listing_id})
        if listing:
            return self._format_listing_context(listing)

        # 3) Try dedicated storage auctions
        listing = await self.db.storage_auctions.find_one({"id": listing_id})
        if listing:
            return self._format_storage_auction_context(listing)

        return ""

    def _format_listing_context(self, listing: Dict[str, Any]) -> str:
        """iter222 — Defensive context builder for general listings.

        Handles storage_locker entries gracefully by ALWAYS reading
        `visible_content_tags` and `storage_metadata` instead of the
        retail-only `condition` / `quantity` fields (which are intentionally
        null for storage lockers). Never raises on missing keys."""
        parts: List[str] = ["\n[LISTING CONTEXT — VERIFIED DATA]"]
        parts.append(f"Title: {listing.get('title') or 'N/A'}")
        parts.append(f"Location: {listing.get('city') or 'N/A'}, {listing.get('region') or 'N/A'}")
        lt = (listing.get("listing_type") or "").lower()

        if lt == "storage_locker":
            parts.append("Listing Type: Storage Locker / Abandoned Unit Auction")
            meta = listing.get("storage_metadata") or {}
            if meta.get("facility_name"):
                parts.append(f"Facility: {meta['facility_name']}")
            if meta.get("locker_size"):
                parts.append(f"Locker Size: {meta['locker_size']}")
            if meta.get("locker_number"):
                parts.append(f"Locker Number: {meta['locker_number']}")
            if meta.get("cleanout_deadline_hours"):
                parts.append(f"Cleanout Deadline: {meta['cleanout_deadline_hours']} hours after auction close")
            if meta.get("security_deposit_amount"):
                parts.append(
                    f"Cleanout Security Deposit: ${meta['security_deposit_amount']} CAD "
                    f"(held via Stripe Authorization, released after verification)"
                )
            tags = listing.get("visible_content_tags") or []
            if tags:
                parts.append(f"Visible Contents (tagged by facility): {', '.join(tags)}")
            else:
                parts.append(
                    "Visible Contents: Not tagged — facility could only see "
                    "closed boxes / sealed containers. Sold as-is."
                )
            parts.append(
                "IMPORTANT: Storage locker auctions sell the ENTIRE unit's "
                "contents as one lot. Condition, quantity, and individual "
                "item details are unknown until cleanout."
            )
        else:
            # Retail listing — standard fields
            if listing.get("category"):
                parts.append(f"Category: {listing['category']}")
            if listing.get("condition"):
                parts.append(f"Condition: {listing['condition']}")
            if listing.get("quantity") and int(listing.get("quantity") or 1) > 1:
                parts.append(
                    f"Quantity: {listing['quantity']} units "
                    f"(bid is {'per item' if listing.get('multiply_hammer_by_quantity') else 'total'})"
                )
            if listing.get("buy_now_price"):
                parts.append(f"Buy Now Price: ${listing['buy_now_price']} {listing.get('currency') or 'CAD'}")

        if listing.get("starting_price") is not None:
            parts.append(f"Starting Price: ${listing['starting_price']} {listing.get('currency') or 'CAD'}")
        if listing.get("current_price") is not None and listing.get("current_price") != listing.get("starting_price"):
            parts.append(f"Current Bid: ${listing['current_price']} {listing.get('currency') or 'CAD'}")
        if listing.get("auction_end_date"):
            parts.append(f"Auction Ends: {listing['auction_end_date']}")
        return "\n".join(parts)

    def _format_storage_auction_context(self, auction: Dict[str, Any]) -> str:
        """Context builder for dedicated storage_auctions collection rows."""
        parts: List[str] = ["\n[STORAGE AUCTION CONTEXT — VERIFIED DATA]"]
        parts.append(f"Facility: {auction.get('facility_name') or 'N/A'}")
        parts.append(f"Location: {auction.get('facility_city') or 'N/A'}, {auction.get('facility_province') or 'N/A'}")
        if auction.get("unit_number"):
            parts.append(f"Unit Number: {auction['unit_number']}")
        if auction.get("unit_size"):
            parts.append(f"Unit Size: {auction['unit_size']}")
        if auction.get("unit_type"):
            parts.append(f"Unit Type: {auction['unit_type']}")
        if auction.get("is_lien_unit"):
            parts.append("Sale Reason: Lien sale (legal possession transfer)")
        tags = auction.get("visible_content_tags") or []
        if tags:
            parts.append(f"Visible Contents: {', '.join(tags)}")
        else:
            parts.append(
                "Visible Contents: Not tagged — sold as-is, contents unknown until cleanout."
            )
        if auction.get("current_bid") is not None:
            parts.append(f"Current Bid: ${auction['current_bid']} CAD")
        if auction.get("end_time"):
            parts.append(f"Auction Ends: {auction['end_time']}")
        return "\n".join(parts)

    def _format_minimal_listing(self, listing: Dict[str, Any], kind: str) -> str:
        return (
            f"\n[{kind.upper()} CONTEXT]\n"
            f"Title: {listing.get('title') or 'N/A'}\n"
            f"Location: {listing.get('city') or 'N/A'}, {listing.get('region') or 'N/A'}"
        )

    def _format_multi_item_obligations(self, listing: Dict[str, Any], obligations: Dict[str, Any]) -> str:
        """Format multi-item lot obligations (facility, site capabilities, terms)."""
        context_parts = ["\n[LOT-SPECIFIC SELLER OBLIGATIONS - VERIFIED DATA]"]
        context_parts.append(f"Auction: {listing.get('title', 'N/A')}")
        context_parts.append(f"Location: {listing.get('city', 'N/A')}, {listing.get('region', 'N/A')}")

        if obligations.get("facility_address"):
            context_parts.append(f"Pickup Address: {obligations['facility_address']}")

        context_parts.append("\n**Site Capabilities:**")
        if obligations.get("has_overhead_crane"):
            context_parts.append(f"- Overhead Crane: YES (Capacity: {obligations.get('crane_capacity', 'N/A')} tons)")
        else:
            context_parts.append("- Overhead Crane: NO")
        if obligations.get("has_loading_dock"):
            context_parts.append(f"- Loading Dock: YES ({obligations.get('loading_dock_type', 'standard')})")
        else:
            context_parts.append("- Loading Dock: NO - Ground level loading only")
        if obligations.get("has_forklift_available"):
            context_parts.append("- Forklift: YES - Available on site")
        else:
            context_parts.append("- Forklift: NO - Buyer must provide")
        if obligations.get("has_scale_on_site"):
            context_parts.append("- Scale: YES")
        if obligations.get("ground_level_loading_only"):
            context_parts.append("- IMPORTANT: Ground level loading ONLY")

        if obligations.get("authorized_personnel_only"):
            context_parts.append(f"\n**Safety Requirements:** {obligations.get('safety_requirements', 'PPE required')}")

        context_parts.append("\n**Shipping & Rigging:**")
        if obligations.get("provides_shipping") == "yes":
            context_parts.append(f"- Seller provides shipping: YES - {obligations.get('shipping_details', 'Contact seller')}")
        else:
            context_parts.append("- Seller provides shipping: NO - Buyer must arrange pickup")

        context_parts.append("\n**Financial Terms:**")
        if obligations.get("custom_exchange_rate"):
            context_parts.append(f"- Exchange Rate: 1 USD = {obligations['custom_exchange_rate']} CAD")
        refund_policy = obligations.get("refund_policy", "non_refundable")
        context_parts.append(f"- Refund Policy: {'FINAL SALE' if refund_policy == 'non_refundable' else obligations.get('refund_terms', 'See terms')}")
        if obligations.get("removal_deadline_days"):
            context_parts.append(f"- Removal Deadline: {obligations['removal_deadline_days']} days after auction close")

        return "\n".join(context_parts)

    def _parse_response(self, content: str, language: str, needs_verification: bool = False) -> Dict:
        """Parse response for rich content (action buttons, product cards)"""
        rich_content = {
            "action_buttons": [],
            "product_cards": [],
            "has_rich_content": False
        }

        if needs_verification:
            rich_content["action_buttons"].append({
                "text": "Verify My Phone" if language == "en" else "Verifier mon telephone",
                "action": "verify_phone", "url": "/verify-phone",
                "style": "primary", "icon": "shield-check"
            })
            rich_content["action_buttons"].append({
                "text": "Add Payment Card" if language == "en" else "Ajouter une carte",
                "action": "add_payment", "url": "/settings?tab=payment",
                "style": "primary", "icon": "credit-card"
            })

        content_lower = content.lower()
        if ("view" in content_lower or "browse" in content_lower) and ("auction" in content_lower or "listing" in content_lower):
            rich_content["action_buttons"].append({
                "text": "Browse Auctions" if language == "en" else "Parcourir les encheres",
                "action": "browse_auctions", "url": "/marketplace",
                "style": "secondary", "icon": "package"
            })
        if "how it works" in content_lower or "learn more" in content_lower:
            rich_content["action_buttons"].append({
                "text": "How It Works" if language == "en" else "Comment ca marche",
                "action": "how_it_works", "url": "/how-it-works",
                "style": "secondary", "icon": "help-circle"
            })
        if "support" in content_lower or "contact" in content_lower:
            rich_content["action_buttons"].append({
                "text": "Contact Support" if language == "en" else "Contacter le support",
                "action": "contact_support", "url": "mailto:support@bidvex.com",
                "style": "secondary", "icon": "mail"
            })

        rich_content["has_rich_content"] = len(rich_content["action_buttons"]) > 0
        return rich_content


# Singleton instance
_assistant = None

def get_assistant(api_key: str, db) -> BidVexAssistant:
    """Get or create assistant singleton"""
    global _assistant
    if _assistant is None:
        _assistant = BidVexAssistant(api_key, db)
    return _assistant
