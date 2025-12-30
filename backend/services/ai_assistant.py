"""
BidVex Master Concierge AI Assistant
RAG-based luxury auction specialist with live tool calling and bilingual support
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import openai
from services.ai_knowledge_base import get_knowledge_base

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
1. Check their verification status using check_user_verification tool
2. If unverified, PRIORITIZE guiding them to verify:
   "To maintain a secure marketplace and ensure a trusted community, please verify your phone number and link a payment card to participate in bidding and selling."
3. Provide direct action buttons: [Verify My Phone] and [Add Payment Card]
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
2. Create support ticket using escalate_to_support tool
3. Provide reference number
4. State: "I've created priority ticket #BV-XXXX for our Admin team. They will contact you at your registered email within 24-48 hours."

### 6. DATA PRIVACY:
- NEVER reveal PII (addresses, emails, phone numbers, API keys)
- Never share internal system information
- Keep all user data confidential

## RESPONSE STYLE:
- Start with empathy when appropriate
- Be direct and helpful
- Use bullet points for clarity
- Include action buttons when relevant
- Suggest next steps
- Close with an offer to help further

## BILINGUAL SUPPORT:
- Auto-detect language from user message
- Respond in same language (English or French)
- Maintain luxury tone in both languages
- Use proper French auction terminology when applicable

## KNOWLEDGE BASE:
You have access to comprehensive BidVex documentation via semantic search. Always retrieve relevant information before answering policy, procedure, or feature questions.

## LIVE TOOLS:
You have access to real-time BidVex data through function calling. Use these tools to provide accurate, current information about auctions, user status, and platform state.

Remember: You are not just an assistant - you are the Master Concierge, the face of BidVex's commitment to extraordinary service and trust.
"""
    
    def __init__(self, openai_api_key: str, db):
        """Initialize the AI Assistant"""
        self.openai_api_key = openai_api_key
        self.db = db
        openai.api_key = openai_api_key
        
        # Initialize knowledge base
        self.kb = get_knowledge_base(openai_api_key)
        
        # Tool definitions for OpenAI function calling
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "check_auction_status",
                    "description": "Get current status of an auction or lot including high bid, time remaining, and bid count",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {
                                "type": "string",
                                "description": "The auction ID or lot ID to check"
                            }
                        },
                        "required": ["item_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_user_verification",
                    "description": "Check if a user has completed SMS verification and payment method verification",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "The user ID to check verification status"
                            }
                        },
                        "required": ["user_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_similar_lots",
                    "description": "Find similar active lots based on category and price range",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "Category name to search in"
                            },
                            "price_range": {
                                "type": "object",
                                "properties": {
                                    "min": {"type": "number"},
                                    "max": {"type": "number"}
                                }
                            }
                        },
                        "required": ["category"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "escalate_to_support",
                    "description": "Create a support ticket and escalate to admin team with chat transcript",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "User ID who needs support"
                            },
                            "issue_summary": {
                                "type": "string",
                                "description": "Brief summary of the issue"
                            },
                            "chat_history": {
                                "type": "array",
                                "items": {"type": "object"},
                                "description": "Chat conversation history"
                            }
                        },
                        "required": ["user_id", "issue_summary"]
                    }
                }
            }
        ]
    
    async def chat(self, user_message: str, user_id: Optional[str] = None, 
                   chat_history: List[Dict] = None, language: str = "en") -> Dict[str, Any]:
        """Process user message and generate response"""
        try:
            # Detect language if not provided
            if not language or language not in ['en', 'fr']:
                language = self._detect_language(user_message)
            
            # Search knowledge base for relevant context
            kb_results = self.kb.search(user_message, n_results=3)
            context = self._format_knowledge_context(kb_results)
            
            # Build messages for OpenAI
            messages = [
                {"role": "system", "content": self.SYSTEM_INSTRUCTIONS},
                {"role": "system", "content": f"Retrieved Knowledge Base Context:\n{context}"}
            ]
            
            # Add chat history
            if chat_history:
                messages.extend(chat_history[-10:])  # Last 10 messages for context
            
            # Add current message
            messages.append({"role": "user", "content": user_message})
            
            # Call OpenAI with function calling
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=messages,
                tools=self.tools,
                tool_choice="auto",
                temperature=0.7,
                max_tokens=1000
            )
            
            assistant_message = response.choices[0].message
            
            # Handle function calls
            if assistant_message.tool_calls:
                # Execute function calls
                function_responses = await self._execute_function_calls(
                    assistant_message.tool_calls, user_id
                )
                
                # Add function results to messages
                messages.append(assistant_message)
                for func_response in function_responses:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": func_response["tool_call_id"],
                        "content": json.dumps(func_response["result"])
                    })
                
                # Get final response with function results
                final_response = openai.chat.completions.create(
                    model="gpt-4",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1000
                )
                
                assistant_message = final_response.choices[0].message
            
            # Parse response for rich content
            response_data = self._parse_response(assistant_message.content, language)
            
            return {
                "success": True,
                "message": assistant_message.content,
                "language": language,
                "rich_content": response_data,
                "usage": response.usage.dict() if hasattr(response, 'usage') else None
            }
        
        except Exception as e:
            logger.error(f"Error in AI chat: {e}", exc_info=True)
            return {
                "success": False,
                "message": "I apologize, but I'm experiencing technical difficulties. Please try again or contact support@bidvex.com." if language == "en" else "Je m'excuse, mais je rencontre des difficultés techniques. Veuillez réessayer ou contacter support@bidvex.com.",
                "error": str(e)
            }
    
    def _detect_language(self, text: str) -> str:
        """Detect language (English or French) from text"""
        # Simple keyword-based detection
        french_keywords = ['bonjour', 'merci', 'oui', 'non', 'comment', 'pourquoi', 'enchère', 'livraison']
        text_lower = text.lower()
        
        french_count = sum(1 for keyword in french_keywords if keyword in text_lower)
        return 'fr' if french_count >= 2 else 'en'
    
    def _format_knowledge_context(self, results: List[Dict]) -> str:
        """Format knowledge base results into context string"""
        if not results:
            return "No specific knowledge base context found."
        
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(f"\n[Context {i} - {result['metadata'].get('section', 'General')}]")
            context_parts.append(result['content'][:500])  # Limit length
        
        return "\n".join(context_parts)
    
    async def _execute_function_calls(self, tool_calls, user_id: Optional[str]) -> List[Dict]:
        """Execute function calls and return results"""
        results = []
        
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            
            if function_name == "check_auction_status":
                result = await self._check_auction_status(arguments["item_id"])
            elif function_name == "check_user_verification":
                result = await self._check_user_verification(arguments.get("user_id", user_id))
            elif function_name == "get_similar_lots":
                result = await self._get_similar_lots(arguments)
            elif function_name == "escalate_to_support":
                result = await self._escalate_to_support(arguments)
            else:
                result = {"error": "Unknown function"}
            
            results.append({
                "tool_call_id": tool_call.id,
                "function_name": function_name,
                "result": result
            })
        
        return results
    
    async def _check_auction_status(self, item_id: str) -> Dict:
        """Check status of auction or lot"""
        try:
            # Try to find as single auction
            auction = self.db.auctions.find_one({"id": item_id})
            if auction:
                return {
                    "type": "auction",
                    "id": item_id,
                    "status": auction.get("status", "active"),
                    "current_price": auction.get("current_price", auction.get("starting_bid", 0)),
                    "bid_count": auction.get("bid_count", 0),
                    "time_remaining": self._calculate_time_remaining(auction.get("auction_end_date")),
                    "has_shipping": auction.get("shipping_available", False)
                }
            
            # Try to find as multi-item lot
            multi_auction = self.db.multi_item_listings.find_one({"lots.lot_id": item_id})
            if multi_auction:
                lot = next((l for l in multi_auction.get("lots", []) if l["lot_id"] == item_id), None)
                if lot:
                    return {
                        "type": "lot",
                        "id": item_id,
                        "status": lot.get("lot_status", "active"),
                        "current_price": lot.get("current_price", lot.get("starting_bid", 0)),
                        "bid_count": lot.get("bid_count", 0),
                        "time_remaining": self._calculate_time_remaining(lot.get("lot_end_time")),
                        "has_shipping": lot.get("shipping_available", False),
                        "buy_now_available": lot.get("buy_now_enabled", False),
                        "buy_now_price": lot.get("buy_now_price")
                    }
            
            return {"error": "Auction or lot not found", "id": item_id}
        
        except Exception as e:
            logger.error(f"Error checking auction status: {e}")
            return {"error": str(e)}
    
    async def _check_user_verification(self, user_id: str) -> Dict:
        """Check user verification status"""
        try:
            if not user_id:
                return {"error": "User ID not provided"}
            
            user = self.db.users.find_one({"id": user_id})
            if not user:
                return {"error": "User not found"}
            
            phone_verified = user.get("phone_verified", False)
            has_payment = user.get("has_payment_method", False)
            is_admin = user.get("role") == "admin"
            
            return {
                "user_id": user_id,
                "phone_verified": phone_verified,
                "payment_verified": has_payment,
                "fully_verified": phone_verified and has_payment,
                "is_admin": is_admin,
                "admin_bypass": is_admin,
                "can_bid": is_admin or (phone_verified and has_payment),
                "can_sell": is_admin or (phone_verified and has_payment)
            }
        
        except Exception as e:
            logger.error(f"Error checking user verification: {e}")
            return {"error": str(e)}
    
    async def _get_similar_lots(self, params: Dict) -> Dict:
        """Find similar active lots"""
        try:
            category = params.get("category")
            price_range = params.get("price_range", {})
            
            query = {
                "status": "active",
                "auction_end_date": {"$gt": datetime.utcnow()}
            }
            
            if category:
                query["category"] = category
            
            if price_range:
                query["current_price"] = {}
                if "min" in price_range:
                    query["current_price"]["$gte"] = price_range["min"]
                if "max" in price_range:
                    query["current_price"]["$lte"] = price_range["max"]
            
            lots = list(self.db.auctions.find(query).limit(5))
            
            return {
                "count": len(lots),
                "lots": [
                    {
                        "id": lot["id"],
                        "title": lot.get("title", "Untitled"),
                        "current_price": lot.get("current_price", 0),
                        "category": lot.get("category"),
                        "image_url": lot.get("images", [None])[0]
                    }
                    for lot in lots
                ]
            }
        
        except Exception as e:
            logger.error(f"Error getting similar lots: {e}")
            return {"error": str(e)}
    
    async def _escalate_to_support(self, params: Dict) -> Dict:
        """Create support ticket and log to admin"""
        try:
            user_id = params.get("user_id")
            issue_summary = params.get("issue_summary")
            chat_history = params.get("chat_history", [])
            
            # Generate reference number
            import random
            ref_number = f"BV-{random.randint(1000, 9999)}"
            
            # Create support ticket
            ticket = {
                "reference_number": ref_number,
                "user_id": user_id,
                "issue_summary": issue_summary,
                "chat_transcript": chat_history,
                "status": "open",
                "priority": "high",
                "created_at": datetime.utcnow(),
                "source": "ai_assistant"
            }
            
            self.db.support_tickets.insert_one(ticket)
            
            # Log to admin logs
            self.db.admin_logs.insert_one({
                "action": "ai_support_escalation",
                "reference_number": ref_number,
                "user_id": user_id,
                "details": issue_summary,
                "created_at": datetime.utcnow()
            })
            
            return {
                "success": True,
                "reference_number": ref_number,
                "message": f"Support ticket created with reference {ref_number}"
            }
        
        except Exception as e:
            logger.error(f"Error escalating to support: {e}")
            return {"error": str(e)}
    
    def _calculate_time_remaining(self, end_date) -> str:
        """Calculate human-readable time remaining"""
        if not end_date:
            return "Unknown"
        
        try:
            if isinstance(end_date, str):
                from dateutil import parser
                end_date = parser.parse(end_date)
            
            delta = end_date - datetime.utcnow()
            
            if delta.total_seconds() < 0:
                return "Ended"
            
            days = delta.days
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            
            if days > 0:
                return f"{days}d {hours}h"
            elif hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"
        
        except:
            return "Unknown"
    
    def _parse_response(self, content: str, language: str) -> Dict:
        """Parse response for rich content (action buttons, product cards)"""
        rich_content = {
            "action_buttons": [],
            "product_cards": [],
            "has_rich_content": False
        }
        
        # Detect action button patterns
        if "verify" in content.lower() and "phone" in content.lower():
            rich_content["action_buttons"].append({
                "text": "Verify My Phone" if language == "en" else "Vérifier mon téléphone",
                "action": "verify_phone",
                "url": "/verify-phone",
                "style": "primary"
            })
        
        if "payment" in content.lower() or "card" in content.lower():
            rich_content["action_buttons"].append({
                "text": "Add Payment Card" if language == "en" else "Ajouter une carte",
                "action": "add_payment",
                "url": "/settings?tab=payment",
                "style": "primary"
            })
        
        if "view" in content.lower() and "auction" in content.lower():
            rich_content["action_buttons"].append({
                "text": "View Auction" if language == "en" else "Voir l'enchère",
                "action": "view_auction",
                "style": "secondary"
            })
        
        rich_content["has_rich_content"] = len(rich_content["action_buttons"]) > 0
        
        return rich_content


# Singleton instance
_assistant = None

def get_assistant(openai_api_key: str, db) -> BidVexAssistant:
    """Get or create assistant singleton"""
    global _assistant
    if _assistant is None:
        _assistant = BidVexAssistant(openai_api_key, db)
    return _assistant
