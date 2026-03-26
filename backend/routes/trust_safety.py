"""
BidVex - Trust & Safety / AI Guard
Auto-extracted from server.py during P2 refactoring.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Query, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from deps import get_db, get_current_user, get_current_user_optional, User
from services.fraud_detection import FLAG_TYPES
from shared import (
    DEFAULT_EMAIL_TEMPLATES, EMAIL_TEMPLATE_CATEGORIES,
    DEFAULT_MARKETPLACE_SETTINGS, AFFILIATE_COMMISSION_RATE,
    generate_affiliate_code, get_email_templates, get_email_template_id,
    get_marketplace_settings, get_epoch_timestamp, get_server_timestamp,
    calculate_buyer_fees, calculate_seller_fees, calculate_stripe_fee_recovery,
    calculate_partner_checkout, calculate_standard_checkout,
    FeeCalculation, UserCreate, Category, Invoice, PaddleNumber,
    PaymentTransaction, SessionCreate, get_minimum_increment,
    STANDARD_BUYER_PREMIUM_RATE, STANDARD_SELLER_COMMISSION_RATE,
    PARTNER_PLATFORM_FEE_RATE, PARTNER_ANNUAL_ACCESS_FEE,
    STRIPE_PERCENTAGE_FEE, STRIPE_FIXED_FEE,
)
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from pathlib import Path
import logging
import uuid
import os as _os
import json as _json

logger = logging.getLogger(__name__)



trust_safety_router = APIRouter(tags=["Trust & Safety"])


async def calculate_trust_score(user_id: str) -> int:
    """Calculate a trust score (0-100) based on user activity and history."""
    db = get_db()
    score = 50  # base score
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        return score
    if user.get("is_verified"):
        score += 15
    if user.get("tax_verified"):
        score += 10
    txn_count = await db.transactions.count_documents({"$or": [{"buyer_id": user_id}, {"seller_id": user_id}]})
    score += min(txn_count * 2, 20)
    fraud_count = await db.fraud_flags.count_documents({"user_id": user_id, "status": "confirmed_fraud"})
    score -= fraud_count * 25
    return max(0, min(100, score))


@trust_safety_router.get("/admin/trust-safety/scores")
async def get_trust_scores(current_user: User = Depends(get_current_user)):
    db = get_db()
    if not current_user.email.endswith("@bidvex.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    users = await db.users.find({}, {"_id": 0, "password": 0}).to_list(100)
    
    scores = []
    for user in users:
        trust_score = await calculate_trust_score(user["id"])
        scores.append({
            "user_id": user["id"],
            "name": user.get("name"),
            "email": user.get("email"),
            "trust_score": trust_score,
            "risk_level": "high" if trust_score < 40 else "medium" if trust_score < 70 else "low"
        })
    
    return sorted(scores, key=lambda x: x["trust_score"])



@trust_safety_router.get("/admin/trust-safety/fraud-flags")
async def get_fraud_flags(current_user: User = Depends(get_current_user)):
    db = get_db()
    if not current_user.email.endswith("@bidvex.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    flags = []
    
    # Duplicate listings detection
    listings = await db.listings.find({"status": "active"}, {"_id": 0}).to_list(1000)
    titles_seen = {}
    for listing in listings:
        title = listing.get("title", "").lower()
        if title in titles_seen:
            flags.append({
                "type": "duplicate_listing",
                "severity": "medium",
                "listing_id": listing["id"],
                "title": listing["title"],
                "description": f"Duplicate of listing {titles_seen[title]}",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        else:
            titles_seen[title] = listing["id"]
    
    # Suspicious pricing detection
    for listing in listings:
        if listing.get("starting_price", 0) > 10000:
            flags.append({
                "type": "suspicious_pricing",
                "severity": "high",
                "listing_id": listing["id"],
                "title": listing["title"],
                "description": f"Unusually high price: ${listing['starting_price']}",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
    
    # High-value bids from new accounts
    bids = await db.bids.find({}, {"_id": 0}).to_list(1000)
    for bid in bids:
        user = await db.users.find_one({"id": bid.get("bidder_id")})
        if user:
            account_age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(user["created_at"])).days
            if account_age_days < 7 and bid.get("amount", 0) > 500:
                flags.append({
                    "type": "new_account_high_bid",
                    "severity": "high",
                    "user_id": user["id"],
                    "user_name": user.get("name"),
                    "bid_amount": bid["amount"],
                    "account_age_days": account_age_days,
                    "description": f"New account ({account_age_days}d old) bidding ${bid['amount']}",
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
    
    return flags



@trust_safety_router.get("/admin/trust-safety/collusion-patterns")
async def detect_collusion(current_user: User = Depends(get_current_user)):
    db = get_db()
    if not current_user.email.endswith("@bidvex.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    patterns = []
    
    # Find buyer-seller pairs with multiple cancelled transactions
    cancelled_listings = await db.listings.find({"status": "cancelled"}, {"_id": 0}).to_list(1000)
    
    pair_counts = {}
    for listing in cancelled_listings:
        # Get winning bid if any
        bids = await db.bids.find({"listing_id": listing["id"]}, {"_id": 0}).sort("amount", -1).limit(1).to_list(1)
        if bids:
            pair = f"{listing['seller_id']}-{bids[0].get('bidder_id')}"
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
    
    # Flag pairs with 3+ cancellations
    for pair, count in pair_counts.items():
        if count >= 3:
            seller_id, buyer_id = pair.split("-")
            seller = await db.users.find_one({"id": seller_id})
            buyer = await db.users.find_one({"id": buyer_id})
            
            patterns.append({
                "type": "repeated_cancellations",
                "severity": "high",
                "seller_id": seller_id,
                "seller_name": seller.get("name") if seller else "Unknown",
                "buyer_id": buyer_id,
                "buyer_name": buyer.get("name") if buyer else "Unknown",
                "cancellation_count": count,
                "description": f"{count} cancelled transactions between same buyer-seller pair",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
    
    return patterns



@trust_safety_router.post("/admin/trust-safety/verify-requirement")
async def enforce_verification_requirement(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    db = get_db()
    if not current_user.email.endswith("@bidvex.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    requirement_type = data.get("type")  # "email" or "phone"
    enabled = data.get("enabled", True)
    
    await db.platform_settings.update_one(
        {"setting_key": f"require_{requirement_type}_verification"},
        {"$set": {"value": enabled, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    
    return {"message": f"{requirement_type.capitalize()} verification requirement {'enabled' if enabled else 'disabled'}"}



@trust_safety_router.get("/admin/ai-guard/flags")
async def get_fraud_flags(
    status: Optional[str] = None,
    flag_type: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Get all fraud flags with optional filters."""
    if current_user.role != 'admin' and not current_user.email.endswith("@bidvex.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    fraud_service = get_fraud_detection_service(db)
    flags = await fraud_service.get_flagged_auctions(status=status, flag_type=flag_type, limit=limit)
    
    return {
        "success": True,
        "flags": flags,
        "total": len(flags),
        "filters": {"status": status, "flag_type": flag_type}
    }



@trust_safety_router.post("/admin/ai-guard/scan")
async def scan_for_fraud(
    hours_back: int = 24,
    current_user: User = Depends(get_current_user)
):
    """Run fraud detection scan on all recent auctions."""
    if current_user.role != 'admin' and not current_user.email.endswith("@bidvex.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    fraud_service = get_fraud_detection_service(db)
    
    try:
        # Run the scan
        flags = await fraud_service.scan_all_auctions(hours_back=hours_back)
        
        # Save all detected flags
        saved_count = 0
        for flag in flags:
            if await fraud_service.save_flag(flag):
                saved_count += 1
        
        return {
            "success": True,
            "flags_detected": len(flags),
            "flags_saved": saved_count,
            "scan_range_hours": hours_back
        }
    except Exception as e:
        logger.error(f"Fraud scan error: {e}")
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")



@trust_safety_router.post("/admin/ai-guard/analyze/{auction_id}")
async def analyze_single_auction(
    auction_id: str,
    current_user: User = Depends(get_current_user)
):
    """Analyze a specific auction for fraud."""
    if current_user.role != 'admin' and not current_user.email.endswith("@bidvex.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    fraud_service = get_fraud_detection_service(db)
    flags = await fraud_service.analyze_auction(auction_id)
    
    # Save any detected flags
    for flag in flags:
        await fraud_service.save_flag(flag)
    
    return {
        "success": True,
        "auction_id": auction_id,
        "flags_detected": len(flags),
        "flags": flags
    }



@trust_safety_router.put("/admin/ai-guard/flags/{flag_id}/status")
async def update_flag_status(
    flag_id: str,
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Update the status of a fraud flag."""
    if current_user.role != 'admin' and not current_user.email.endswith("@bidvex.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    new_status = data.get("status")
    notes = data.get("notes")
    
    if new_status not in FLAG_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {FLAG_STATUSES}")
    
    fraud_service = get_fraud_detection_service(db)
    success = await fraud_service.update_flag_status(
        flag_id=flag_id,
        new_status=new_status,
        admin_id=current_user.id,
        notes=notes
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Flag not found or update failed")
    
    return {
        "success": True,
        "flag_id": flag_id,
        "new_status": new_status
    }



@trust_safety_router.post("/admin/ai-guard/suspend/{auction_id}")
async def suspend_auction(
    auction_id: str,
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Suspend an auction due to fraud concerns."""
    if current_user.role != 'admin' and not current_user.email.endswith("@bidvex.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    reason = data.get("reason", "Suspended for fraud investigation")
    
    fraud_service = get_fraud_detection_service(db)
    success = await fraud_service.suspend_auction(
        auction_id=auction_id,
        admin_id=current_user.id,
        reason=reason
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Auction not found or suspension failed")
    
    return {
        "success": True,
        "auction_id": auction_id,
        "status": "suspended",
        "reason": reason
    }



@trust_safety_router.post("/admin/ai-guard/summary/{flag_id}")
async def generate_flag_summary(
    flag_id: str,
    current_user: User = Depends(get_current_user)
):
    """Generate AI-powered fraud summary for a flag."""
    if current_user.role != 'admin' and not current_user.email.endswith("@bidvex.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get the flag from database
    flag = await db.fraud_flags.find_one({"id": flag_id}, {"_id": 0})
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    
    fraud_service = get_fraud_detection_service(db)
    summary = await fraud_service.generate_fraud_summary(flag)
    
    # Save summary to flag
    await db.fraud_flags.update_one(
        {"id": flag_id},
        {"$set": {"ai_summary": summary, "summary_generated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {
        "success": True,
        "flag_id": flag_id,
        "summary": summary
    }



@trust_safety_router.get("/admin/ai-guard/stats")
async def get_fraud_stats(current_user: User = Depends(get_current_user)):
    """Get fraud detection statistics."""
    db = get_db()
    if current_user.role != 'admin' and not current_user.email.endswith("@bidvex.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get counts by status
    total = await db.fraud_flags.count_documents({})
    pending = await db.fraud_flags.count_documents({"status": "pending_review"})
    investigating = await db.fraud_flags.count_documents({"status": "under_investigation"})
    cleared = await db.fraud_flags.count_documents({"status": "cleared"})
    confirmed = await db.fraud_flags.count_documents({"status": "confirmed_fraud"})
    
    # Get counts by flag type
    type_counts = {}
    for flag_type in FLAG_TYPES.keys():
        type_counts[flag_type] = await db.fraud_flags.count_documents({"flag_type": flag_type})
    
    return {
        "success": True,
        "stats": {
            "total": total,
            "pending_review": pending,
            "under_investigation": investigating,
            "cleared": cleared,
            "confirmed_fraud": confirmed,
            "by_type": type_counts
        }
    }

# PHASE 2: AI INTEGRATION



@trust_safety_router.post("/admin/trust-safety/analyze-content")
async def analyze_content_ai(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@bidvex.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    content = data.get("content")
    content_type = data.get("type", "text")  # "text" or "image"
    
    try:
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(api_key=EMERGENT_LLM_KEY)
        
        prompt = f"""Analyze this content for scams, fraud, or policy violations.
        
Content: {content}

Provide a risk assessment with:
1. Risk Level (low/medium/high)
2. Detected Issues (list)
3. Recommended Action
4. Confidence Score (0-100)

Respond in JSON format."""

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=512,
        )
        
        analysis = response.choices[0].message.content
        
        return {
            "analysis": analysis,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"AI analysis error: {str(e)}")
        return {
            "error": str(e),
            "analysis": "AI analysis unavailable"
        }



@trust_safety_router.post("/admin/trust-safety/scan-listing")
async def scan_listing_ai(listing_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    if not current_user.email.endswith("@bidvex.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    try:
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(api_key=EMERGENT_LLM_KEY)
        
        content_to_analyze = f"Title: {listing.get('title')}\nDescription: {listing.get('description')}\nPrice: ${listing.get('starting_price')}"
        
        prompt = f"""Analyze this auction listing for fraud indicators:

{content_to_analyze}

Check for:
- Scam keywords
- Unrealistic pricing
- Stolen/duplicate content indicators
- Off-platform contact attempts
- Too-good-to-be-true offers

Provide risk assessment in JSON format with risk_level, issues, and recommendations."""

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=512,
        )
        
        analysis = response.choices[0].message.content
        
        # Store analysis result
        await db.listing_scans.insert_one({
            "id": str(uuid.uuid4()),
            "listing_id": listing_id,
            "analysis": analysis,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "scanned_by": current_user.id
        })
        
        return {
            "listing_id": listing_id,
            "analysis": analysis,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Listing scan error: {str(e)}")
        return {"error": str(e)}



@trust_safety_router.post("/admin/trust-safety/scan-messages")
async def scan_messages_ai(conversation_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    if not current_user.email.endswith("@bidvex.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    messages = await db.messages.find({"conversation_id": conversation_id}, {"_id": 0}).to_list(100)
    
    scam_keywords = ["whatsapp", "telegram", "crypto", "send money", "wire transfer", "gift card", "outside platform", "direct payment"]
    
    flagged_messages = []
    for msg in messages:
        content_lower = msg.get("content", "").lower()
        found_keywords = [kw for kw in scam_keywords if kw in content_lower]
        
        if found_keywords:
            flagged_messages.append({
                "message_id": msg["id"],
                "content": msg["content"],
                "keywords_found": found_keywords,
                "sender_id": msg.get("sender_id"),
                "severity": "high" if len(found_keywords) > 2 else "medium"
            })
            
            # Auto-flag the message
            await db.messages.update_one({"id": msg["id"]}, {"$set": {"flagged": True, "flagged_reason": f"Scam keywords: {', '.join(found_keywords)}"}})
    
    return {
        "conversation_id": conversation_id,
        "flagged_count": len(flagged_messages),
        "flagged_messages": flagged_messages
    }

# PHASE 3: ADVANCED BEHAVIORAL ANALYSIS



@trust_safety_router.get("/admin/trust-safety/behavioral-analysis")
async def behavioral_analysis(user_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    if not current_user.email.endswith("@bidvex.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Analyze bidding patterns
    bids = await db.bids.find({"bidder_id": user_id}, {"_id": 0}).to_list(1000)
    bid_amounts = [b.get("amount", 0) for b in bids]
    avg_bid = sum(bid_amounts) / len(bid_amounts) if bid_amounts else 0
    
    # Analyze messaging patterns
    messages_sent = await db.messages.count_documents({"sender_id": user_id})
    flagged_messages = await db.messages.count_documents({"sender_id": user_id, "flagged": True})
    
    # Analyze transaction patterns
    completed_transactions = await db.payment_transactions.count_documents({"user_id": user_id, "payment_status": "paid"})
    failed_transactions = await db.payment_transactions.count_documents({"user_id": user_id, "payment_status": "failed"})
    
    # Calculate risk indicators
    risk_indicators = []
    if flagged_messages > 0:
        risk_indicators.append(f"{flagged_messages} flagged messages")
    if failed_transactions > completed_transactions:
        risk_indicators.append("More failed than completed transactions")
    if len(bids) > 20 and completed_transactions == 0:
        risk_indicators.append("Many bids but no completed purchases")
    
    behavior_score = 100
    behavior_score -= flagged_messages * 15
    behavior_score -= (failed_transactions * 5)
    behavior_score = max(0, behavior_score)
    
    return {
        "user_id": user_id,
        "name": user.get("name"),
        "behavior_score": behavior_score,
        "risk_level": "high" if behavior_score < 40 else "medium" if behavior_score < 70 else "low",
        "statistics": {
            "total_bids": len(bids),
            "average_bid": avg_bid,
            "messages_sent": messages_sent,
            "flagged_messages": flagged_messages,
            "completed_transactions": completed_transactions,
            "failed_transactions": failed_transactions
        },
        "risk_indicators": risk_indicators,
        "recommended_actions": [
            "Suspend messaging" if flagged_messages > 2 else None,
            "Require re-verification" if behavior_score < 50 else None,
            "Manual review required" if len(risk_indicators) > 2 else None
        ]
    }



@trust_safety_router.post("/admin/trust-safety/auto-action")
async def execute_auto_action(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    db = get_db()
    if not current_user.email.endswith("@bidvex.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user_id = data.get("user_id")
    action = data.get("action")  # "suspend_messaging", "require_verification", "suspend_account"
    reason = data.get("reason", "Automated safety action")
    
    if action == "suspend_messaging":
        await db.users.update_one({"id": user_id}, {"$set": {"messaging_suspended": True, "suspension_reason": reason}})
    elif action == "require_verification":
        await db.users.update_one({"id": user_id}, {"$set": {"email_verified": False, "phone_verified": False, "verification_required": True}})
    elif action == "suspend_account":
        await db.users.update_one({"id": user_id}, {"$set": {"status": "suspended", "suspension_reason": reason}})
    
    # Log the action
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()),
        "admin_id": "SYSTEM_AUTO",
        "admin_email": "system@bazario.com",
        "action": f"auto_{action}",
        "target_type": "user",
        "target_id": user_id,
        "details": reason,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {"message": f"Auto-action '{action}' executed for user {user_id}"}


