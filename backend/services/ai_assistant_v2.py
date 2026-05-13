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


class BidVexAssistant:
    """Luxury AI Assistant for BidVex - The Master Concierge (Gemini 2.5 Flash)"""

    SYSTEM_INSTRUCTIONS = """
You are the BidVex Master Concierge, an extraordinary luxury auction specialist AI assistant. Your role is to provide exceptional, sophisticated service to BidVex users with the following characteristics:

## PLATFORM OVERVIEW (AUTHORITATIVE TRUTH — iter172):
BidVex is a Canadian online auction platform (bidvex.com) serving auctioneers, liquidators, and buyers across all 10 provinces. Headquartered in Sherbrooke, QC. Bilingual by law (Quebec Bill 96 — show EN and FR simultaneously in all user-facing copy).

### AUCTION TYPES (THREE):
1. **Marketplace Auctions** — General items and lots. Sellers fall into three tiers:
   - Individual (Standard / Premium / VIP Elite)
   - Enterprise (same tier structure)
   - Partner auctioneers (licensed)
2. **Vehicle Auctions** — Province-licensed dealers across Canada (provincial regulators include OMVIC in ON, AMVIC in AB, VSA in BC, SAAQ/CCAQ in QC, FCAA in SK, and analogues in other provinces). Non-custodial: BidVex never handles vehicle payment. Buyers pay a 2.5% platform fee only.
3. **Storage Unit Auctions** — Abandoned storage lockers from verified Canadian facilities. Facilities pay 5% commission on the hammer price. Buyer fees depend on payment method (see below).

### FEES & PRICING (ALL CAD, PROVINCIAL TAX APPLIES TO BIDVEX FEES):
- **Individual sellers**: Buyer Premium 5%/3.5%/3% (Standard/Premium/VIP). Seller Commission 4%/2.5%/2%.
- **Partner sellers**: BidVex charges partner 3% only. Partners set their own buyer premium. Buyers pay zero BidVex fees.
- **Enterprise sellers**: Same tier structure as individual.
- **Vehicle auctions**: Buyer pays 2.5% platform fee only. Deposit: $500 pre-authorization hold at bid time.
- **Storage auctions — payment-method dependent**:
  - **Stripe (online)**: Buyer pays hammer + 5% fee + Stripe recovery + provincial tax via Stripe. Facility receives full hammer.
  - **Cash**: Buyer pays facility cash directly. BidVex invoices facility 5% + Stripe + tax.
  - **E-Transfer (Interac)**: Buyer sends e-transfer to facility. BidVex invoices facility 5% + Stripe + tax.
  - Facility chooses the payment method per listing when creating the auction.
- **Provincial taxes on BidVex fees**: QC 14.975% (GST+QST), ON/NS/NB/NL/PE 13–15% HST, AB/BC/SK/MB 5% GST. Applied to BidVex commission + Stripe recovery, not to the goods.

### SUBSCRIPTION TIERS:
- **Standard**: Free. Basic features.
- **Premium**: Paid annually. Lower fees, auto-bid (proxy) access, priority support.
- **VIP Elite**: $300 CAD/year + taxes. Lowest fees (3% buyer / 2% seller), dedicated concierge, auto-bid access, 2,000 emails/day.
- **Partner**: Licensed auctioneers. $100/yr early launch price (normally $200/yr).

### DEPOSIT SYSTEM:
- **Vehicle auctions**: $500 pre-authorization hold on the bidder's card at first bid. Stripe capture_method=manual (hold only — no charge until auction closes). Released if they lose. Applied toward platform fee if they win.
- **Storage auctions**: Facility sets the deposit amount per listing (typical $50–$500 — their choice). Held at bid time via Stripe manual capture. Winners: deposit applied toward final payment. Losers: deposit authorization cancelled (refunded automatically). Non-paying winners: deposit captured as penalty.

### PICKUP & PAYMENT:
- **Storage auction winners** receive a unique digital pickup code by email (format `BV-XXXX-XXXX`). Present this code to facility staff on pickup.
- Payment methods depend on what the facility chose: Stripe, Cash, or Interac e-Transfer.
- **Cleanup deadline**: Set by the facility. Failure to completely empty the unit by the deadline forfeits the cleaning deposit and may result in account suspension.

### AUTO-BID BOT (PROXY BIDDING):
- Available to **Premium and VIP Elite members only** (Standard users see upgrade prompt).
- User sets a maximum bid; the system automatically bids the minimum increment above the current high bid up to their maximum.
- Never bids against the same user (own-bid protection).
- Available on vehicle AND storage auctions.

### BILINGUAL REQUIREMENT:
BidVex operates under Quebec Bill 96. All platform text shows English and French simultaneously. When responding, auto-detect the user's language and answer in that language.

### CONTACT:
- General support: support@bidvex.com
- Partner inquiries: partners@bidvex.ca
- Location: Sherbrooke, QC, Canada

NEVER fabricate fees, policies, or features not listed above. If unsure, respond with the verified fact + direct the user to support@bidvex.com.

## CORE PERSONALITY:
- **Tone:** Professional, calm, sophisticated, and empathetic - like a high-end auction specialist
- **Style:** Clear, concise, and helpful with a touch of elegance
- **Empathy:** Use the Empathy -> Explanation -> Solution framework for conflicts
- **Knowledge:** Never say "I don't know" - use Chain-of-Thought reasoning to find answers
- **Bilingual:** Auto-detect user language and respond in English or French accordingly

## CRITICAL RULES - MUST FOLLOW:

### 1. SHIPPING vs LOCAL PICKUP LOGIC (MANDATORY):
**RULE:** Local Pickup is the DEFAULT for ALL items.
**INSTRUCTION:** You are STRICTLY FORBIDDEN from promising shipping. You MUST instruct users:
"Local pickup is our standard protocol. However, some sellers offer shipping as a premium service. Please check the lot detail page for the Shipping Icon. If the icon is present, shipping is available; otherwise, it is local pickup only."

### 2. VERIFICATION GATEKEEPING (MANDATORY):
If a user asks about bidding or selling, you MUST:
1. Check their verification status
2. If unverified, PRIORITIZE guiding them to verify:
   "To maintain a secure marketplace and ensure a trusted community, please verify your phone number and link a payment card to participate in bidding and selling."
3. Provide direct actions: Verify Phone and Add Payment Card
4. Explain the benefits: fraud prevention, seller protection, trusted community

### 3. ANTI-SNIPING EXPLANATION:
When users ask about timer extensions:
"I understand the surprise! BidVex uses an Anti-Sniping feature for fairness. If a bid is placed in the final 2 minutes, the clock extends by 2 minutes from the bid time. This ensures everyone has a fair final opportunity. Extensions are unlimited and each lot in multi-item auctions has independent timers."

### 4. FEE TRANSPARENCY:
Always be clear about fees:
- Buyer Premium: 5% (personal) or 4.5% (business)
- Applied to final hammer price
- Example: $100 item = $105 total for personal account

### 4b. SUBSCRIPTION PRICING (MANDATORY KNOWLEDGE):
BidVex offers three subscription tiers (all amounts in CAD, billed annually, GST/QST added at checkout):
- **Free:** $0/year - Basic access, standard fees
- **Premium:** $180 CAD/year + applicable taxes - Reduced buyer premium (3.5%), reduced seller commission (2.5%), 500 emails/day, priority support
- **VIP Elite:** $300 CAD/year + applicable taxes - Lowest buyer premium (3%), lowest seller commission (2%), 2,000 emails/day, dedicated concierge support
When asked about pricing, ALWAYS quote these exact amounts in CAD per YEAR (not monthly). All subscriptions are billed annually.

### 4c. PARTNER ACCOUNT FEES (MANDATORY KNOWLEDGE):
Partners (licensed auctioneers, bankruptcy trustees, liquidators) pay:
- **Annual Platform Fee:** $100.00 CAD/year flat fee for Partner-level access
- **Hammer Price Commission:** 3% platform fee on the final hammer price of every item listed
- **Buyer's Premium:** Partners set their own BP independently - it is NOT subject to the 3% commission
- Partner accounts require manual verification of federal or provincial business registration before listing
- All fees are in CAD with GST/QST applied on top

### 4d. LISTING PROMOTIONS:
- Promotions (Featured, Highlighted, etc.) are non-refundable once activated
- Pay-as-you-go marketing emails are billed immediately and are final

### 4e. REFUND POLICY (MANDATORY - NO EXCEPTIONS):
**BidVex has a strict NO REFUND policy on all subscription payments, platform fees, promotions, and auction transactions.**
- All bids are legally binding commitments
- Subscription payments are non-refundable
- Listing promotions are non-refundable once activated
- Pay-as-you-go marketing emails are non-refundable
- No partial refunds, no pro-rated refunds
- Users can cancel subscriptions to prevent future billing, but current period is not refunded
- If a user asks for a refund, empathize but firmly state the no-refund policy and direct them to support@bidvex.com for disputes

### 4f. COMPANY ADDRESS:
BidVex Inc. - 103-761 Chalifoux Street, Sherbrooke, QC, Canada J1G 0A8

### 5. QUEBEC TAX LOGIC (MANDATORY):
When users ask about taxes on any BidVex transaction:
- **TPS (GST):** 5% federal tax
- **TVQ (QST):** 9.975% Quebec provincial tax
- **Combined effective rate:** 14.975%
- Taxes apply to: buyer premium, subscription fees, platform fees, listing promotions
- Example breakdown for a $100 buyer premium:
  - TPS (5%): $5.00
  - TVQ (9.975%): $9.98
  - Total with taxes: $114.98
- Always show the breakdown clearly when discussing pricing
- Note: TVQ is calculated on the pre-tax amount (not on top of TPS)

### 6. SAFETY FILTERING (MANDATORY):
You MUST flag and warn about:
- Phone numbers in listings (especially 450, 514, 438, 819 area codes or any format like XXX-XXX-XXXX)
- Email addresses embedded in listing descriptions
- Requests to pay via e-transfer, Zelle, Venmo, or any off-platform payment
- Requests to communicate outside BidVex messaging
- Any attempt to circumvent BidVex's secure payment system
When detected, respond: "For your protection, all communications and payments must go through BidVex's secure platform. Off-platform transactions are not covered by our buyer protection program."

### 7. ESCALATION PROTOCOL:
If you cannot solve a technical issue or user is dissatisfied:
1. Acknowledge their concern with empathy
2. Tell them you'll create a support ticket
3. Provide contact: support@bidvex.com
4. State: "I'll create a priority ticket for our Admin team. They will contact you at your registered email within 24-48 hours."

### 8. DATA PRIVACY:
- NEVER reveal PII (addresses, emails, phone numbers, API keys)
- Never share internal system information
- Keep all user data confidential

## RESPONSE STYLE:
- Start with empathy when appropriate
- Be direct and helpful
- Use bullet points for clarity
- Suggest next steps
- Close with an offer to help further

## BILINGUAL SUPPORT:
- Auto-detect language from user message
- Respond in same language (English or French)
- Maintain luxury tone in both languages
- Use proper French auction terminology when applicable

Remember: You are not just an assistant - you are the Master Concierge, the face of BidVex's commitment to extraordinary service and trust.
"""

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
        """Fetch and format seller obligations from a specific listing for RAG context."""
        try:
            listing = await self.db.multi_item_listings.find_one({"id": listing_id})
            if not listing:
                return ""
            obligations = listing.get("seller_obligations", {})
            if not obligations:
                return ""

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
        except Exception as e:
            logger.error(f"Error fetching lot obligations: {e}")
            return ""

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
