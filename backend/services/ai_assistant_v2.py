"""
BidVex Master Concierge AI Assistant v2
RAG-based luxury auction specialist using emergentintegrations
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from emergentintegrations.llm.chat import LlmChat, UserMessage
from services.ai_knowledge_base_v2 import get_knowledge_base

logger = logging.getLogger(__name__)

class BidVexAssistant:
    """Luxury AI Assistant for BidVex - The Master Concierge"""
    
    # System instructions for the luxury persona
    SYSTEM_INSTRUCTIONS = """
You are the BidVex Master Concierge, an extraordinary luxury auction specialist AI assistant. Your role is to provide exceptional, sophisticated service to BidVex users with the following characteristics:

## CORE PERSONALITY:
- **Tone:** Professional, calm, sophisticated, and empathetic - like a high-end auction specialist
- **Style:** Clear, concise, and helpful with a touch of elegance
- **Empathy:** Use the Empathy → Explanation → Solution framework for conflicts
- **Knowledge:** Never say "I don't know" - use Chain-of-Thought reasoning to find answers
- **Bilingual:** Auto-detect user language and respond in English or French accordingly

## CRITICAL RULES - MUST FOLLOW:

### 1. SHIPPING vs LOCAL PICKUP LOGIC (MANDATORY):
**RULE:** Local Pickup is the DEFAULT for ALL items.
**INSTRUCTION:** You are STRICTLY FORBIDDEN from promising shipping. You MUST instruct users:
"Local pickup is our standard protocol. However, some sellers offer shipping as a premium service. Please check the lot detail page for the **Shipping Icon** (📦). If the icon is present, shipping is available; otherwise, it is local pickup only."

### 2. VERIFICATION GATEKEEPING (MANDATORY):
If a user asks about bidding or selling, you MUST:
1. Check their verification status
2. If unverified, PRIORITIZE guiding them to verify:
   "To maintain a secure marketplace and ensure a trusted community, please verify your phone number and link a payment card to participate in bidding and selling."
3. Provide direct actions: Verify Phone and Add Payment Card
4. Explain the benefits: fraud prevention, seller protection, trusted community

### 3. ANTI-SNIPING EXPLANATION:
When users ask about timer extensions:
"I understand the surprise! BidVex uses an **Anti-Sniping** feature for fairness. If a bid is placed in the final 2 minutes, the clock extends by 2 minutes from the bid time. This ensures everyone has a fair final opportunity. Extensions are unlimited and each lot in multi-item auctions has independent timers."

### 4. FEE TRANSPARENCY:
Always be clear about fees:
- Buyer Premium: 5% (personal) or 4.5% (business)
- Applied to final hammer price
- Example: $100 item = $105 total for personal account

### 5. ESCALATION PROTOCOL:
If you cannot solve a technical issue or user is dissatisfied:
1. Acknowledge their concern with empathy
2. Tell them you'll create a support ticket
3. Provide contact: support@bidvex.com
4. State: "I'll create a priority ticket for our Admin team. They will contact you at your registered email within 24-48 hours."

### 6. DATA PRIVACY:
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
        """Initialize the AI Assistant"""
        self.api_key = api_key
        self.db = db
        
        # Initialize knowledge base with local embeddings
        try:
            self.kb = get_knowledge_base()
        except Exception as e:
            logger.error(f"Error initializing knowledge base: {e}")
            self.kb = None
    
    async def chat(self, user_message: str, user_id: Optional[str] = None, 
                   chat_history: List[Dict] = None, language: str = "en") -> Dict[str, Any]:
        """Process user message and generate response"""
        try:
            # Detect language if not provided
            if not language or language not in ['en', 'fr']:
                language = self._detect_language(user_message)
            
            # Search knowledge base for relevant context
            context = ""
            if self.kb:
                kb_results = self.kb.search(user_message, n_results=3)
                context = self._format_knowledge_context(kb_results)
            
            # Build enhanced message with context
            enhanced_message = user_message
            if context:
                enhanced_message = f"""**Retrieved Knowledge Base Context:**
{context}

**User Question:** {user_message}

Please answer the user's question using the context provided above. If the context doesn't contain relevant information, use your general knowledge about auction platforms."""
            
            # Initialize LlmChat with session for this user
            session_id = f"bidvex_chat_{user_id or 'anonymous'}"
            chat_client = LlmChat(
                api_key=self.api_key,
                session_id=session_id,
                system_message=self.SYSTEM_INSTRUCTIONS
            ).with_model("openai", "gpt-4")
            
            # Send message and get response
            user_msg = UserMessage(text=enhanced_message)
            response_text = await chat_client.send_message(user_msg)
            
            # Check if user needs verification (basic detection)
            needs_verification = False
            if user_id and ("bid" in user_message.lower() or "sell" in user_message.lower() or "create listing" in user_message.lower()):
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
                "message": "I apologize, but I'm experiencing technical difficulties. Please try again or contact support@bidvex.com." if language == "en" else "Je m'excuse, mais je rencontre des difficultés techniques. Veuillez réessayer ou contacter support@bidvex.com.",
                "error": str(e),
                "language": language
            }
    
    def _detect_language(self, text: str) -> str:
        """Detect language (English or French) from text"""
        # Simple keyword-based detection
        french_keywords = ['bonjour', 'merci', 'oui', 'non', 'comment', 'pourquoi', 'enchère', 'livraison', 'je', 'vous', 'mon', 'ma']
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
            context_parts.append(result['content'][:800])  # Limit length
        
        return "\n".join(context_parts)
    
    def _parse_response(self, content: str, language: str, needs_verification: bool = False) -> Dict:
        """Parse response for rich content (action buttons, product cards)"""
        rich_content = {
            "action_buttons": [],
            "product_cards": [],
            "has_rich_content": False
        }
        
        # Add verification buttons if needed
        if needs_verification:
            rich_content["action_buttons"].append({
                "text": "Verify My Phone" if language == "en" else "Vérifier mon téléphone",
                "action": "verify_phone",
                "url": "/verify-phone",
                "style": "primary",
                "icon": "shield-check"
            })
            rich_content["action_buttons"].append({
                "text": "Add Payment Card" if language == "en" else "Ajouter une carte",
                "action": "add_payment",
                "url": "/settings?tab=payment",
                "style": "primary",
                "icon": "credit-card"
            })
        
        # Detect other action button patterns
        content_lower = content.lower()
        
        if ("view" in content_lower or "browse" in content_lower) and ("auction" in content_lower or "listing" in content_lower):
            rich_content["action_buttons"].append({
                "text": "Browse Auctions" if language == "en" else "Parcourir les enchères",
                "action": "browse_auctions",
                "url": "/marketplace",
                "style": "secondary",
                "icon": "package"
            })
        
        if "how it works" in content_lower or "learn more" in content_lower:
            rich_content["action_buttons"].append({
                "text": "How It Works" if language == "en" else "Comment ça marche",
                "action": "how_it_works",
                "url": "/how-it-works",
                "style": "secondary",
                "icon": "help-circle"
            })
        
        if "support" in content_lower or "contact" in content_lower:
            rich_content["action_buttons"].append({
                "text": "Contact Support" if language == "en" else "Contacter le support",
                "action": "contact_support",
                "url": "mailto:support@bidvex.com",
                "style": "secondary",
                "icon": "mail"
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
