"""
BidVex Messages Router
Handles all messaging-related API endpoints including:
- Conversations
- Messages
- File attachments
- Item details sharing
- Automated auction handshakes
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
import os
import logging

logger = logging.getLogger(__name__)

messages_router = APIRouter(prefix="/messages", tags=["Messages"])


def get_db():
    """Get database instance - will be set by main app"""
    from server import db
    return db


def get_messaging_manager():
    """Get messaging WebSocket manager"""
    from server import messaging_manager
    return messaging_manager


def get_notification_manager():
    """Get notification WebSocket manager"""
    from server import notification_manager
    return notification_manager


async def get_current_user_dependency():
    """Get current user dependency"""
    from server import get_current_user
    return get_current_user


# ========== ATTACHMENT UPLOAD ==========
@messages_router.post("/attachment")
async def upload_message_attachment(
    file: UploadFile = File(...),
    receiver_id: str = Form(...),
    conversation_id: str = Form(...),
    current_user = Depends(get_current_user_dependency)
):
    """
    Upload a file attachment in a message conversation (Max 10MB)
    Supported formats: JPG, PNG, GIF, WebP, PDF
    """
    db = get_db()
    
    # Validate file size (10MB max)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be less than 10MB")
    
    # Validate file type
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'application/pdf']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, GIF, WebP and PDF files are allowed")
    
    # Generate unique filename
    file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'bin'
    unique_filename = f"msg_{conversation_id}_{uuid4().hex[:8]}.{file_ext}"
    
    # Store file
    upload_dir = Path("uploads/messages")
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / unique_filename
    
    with open(file_path, "wb") as f:
        f.write(contents)
    
    # Get the base URL for the file
    base_url = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
    file_url = f"{base_url}/api/uploads/messages/{unique_filename}"
    
    # Create message with attachment
    message_id = str(uuid4())
    message = {
        "id": message_id,
        "conversation_id": conversation_id,
        "sender_id": current_user.id,
        "receiver_id": receiver_id,
        "content": "",
        "message_type": "attachment",
        "attachments": [{
            "url": file_url,
            "name": file.filename,
            "type": file.content_type,
            "size": len(contents)
        }],
        "is_read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.messages.insert_one(message)
    
    # Update conversation last message
    await db.conversations.update_one(
        {"id": conversation_id},
        {"$set": {
            "last_message": f"📎 {file.filename}",
            "last_message_time": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Notify via WebSocket
    try:
        messaging_manager = get_messaging_manager()
        await messaging_manager.send_message(conversation_id, {
            "type": "NEW_MESSAGE",
            "message": message
        })
    except Exception as e:
        logger.warning(f"Could not send WebSocket notification: {e}")
    
    return {"status": "success", "message": message}


# ========== SHARE ITEM DETAILS ==========
@messages_router.post("/share-item-details")
async def share_item_details_in_chat(
    data: Dict[str, str],
    current_user = Depends(get_current_user_dependency)
):
    """
    Share item/listing details as a rich card in the chat
    Used by sellers to share lot summaries with buyers
    """
    db = get_db()
    conversation_id = data.get("conversation_id")
    listing_id = data.get("listing_id")
    
    if not conversation_id or not listing_id:
        raise HTTPException(status_code=400, detail="conversation_id and listing_id are required")
    
    # Get conversation
    convo = await db.conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Verify user is part of conversation
    if current_user.id not in convo.get("participants", []):
        raise HTTPException(status_code=403, detail="You are not part of this conversation")
    
    # Get listing details
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
    
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    # Verify current user is the seller
    if listing.get("seller_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Only the seller can share item details")
    
    # Get receiver ID
    receiver_id = [p for p in convo.get("participants", []) if p != current_user.id][0]
    
    # Check payment status
    transaction = await db.payment_transactions.find_one({
        "listing_id": listing_id,
        "buyer_id": receiver_id
    }, {"_id": 0})
    
    payment_status = transaction.get("status", "pending") if transaction else "pending"
    
    # Create item details message
    message_id = str(uuid4())
    item_data = {
        "title": listing.get("title"),
        "description": listing.get("description", "")[:200],
        "image": listing.get("images", [None])[0],
        "final_price": listing.get("current_price") or listing.get("final_price") or listing.get("starting_price", 0),
        "payment_status": payment_status,
        "listing_id": listing_id
    }
    
    message = {
        "id": message_id,
        "conversation_id": conversation_id,
        "sender_id": current_user.id,
        "receiver_id": receiver_id,
        "content": f"Here are the details for {listing.get('title')}",
        "message_type": "item_details",
        "item_data": item_data,
        "is_read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.messages.insert_one(message)
    
    # Update conversation
    await db.conversations.update_one(
        {"id": conversation_id},
        {"$set": {
            "last_message": f"📦 Shared item details: {listing.get('title')}",
            "last_message_time": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Notify via WebSocket
    try:
        messaging_manager = get_messaging_manager()
        await messaging_manager.send_message(conversation_id, {
            "type": "NEW_MESSAGE",
            "message": message
        })
    except Exception as e:
        logger.warning(f"Could not send WebSocket notification: {e}")
    
    return {"status": "success", "message": message}


# ========== AUTOMATED HANDSHAKE (AUCTION WON) ==========
async def create_auction_won_conversation(
    db,
    listing_id: str,
    seller_id: str,
    winner_id: str,
    final_price: float,
    item_title: str
) -> Optional[str]:
    """
    Automatically create a conversation between seller and winning bidder
    when an auction ends. Called from the auction end handler.
    
    Returns the conversation_id if successful, None otherwise.
    """
    try:
        # Check if conversation already exists
        existing = await db.conversations.find_one({
            "participants": {"$all": [seller_id, winner_id]},
            "listing_id": listing_id
        })
        
        if existing:
            conversation_id = existing["id"]
        else:
            # Create new conversation
            conversation_id = str(uuid4())
            conversation = {
                "id": conversation_id,
                "participants": [seller_id, winner_id],
                "listing_id": listing_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "last_message": "🎉 Auction won! Contact details shared.",
                "last_message_time": datetime.now(timezone.utc).isoformat()
            }
            await db.conversations.insert_one(conversation)
        
        # Get seller details
        seller = await db.users.find_one({"id": seller_id}, {"_id": 0})
        
        # Create "Winning Handshake" system message
        message_id = str(uuid4())
        system_message = {
            "id": message_id,
            "conversation_id": conversation_id,
            "sender_id": "system",
            "receiver_id": winner_id,
            "content": f"Congratulations! You have won the auction for {item_title}.",
            "message_type": "auction_won",
            "system_data": {
                "item_title": item_title,
                "final_price": final_price,
                "listing_id": listing_id,
                "seller_name": seller.get("name") if seller else "Seller",
                "seller_email": seller.get("email") if seller else None,
                "seller_phone": seller.get("phone") if seller else None
            },
            "is_read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.messages.insert_one(system_message)
        
        logger.info(f"✅ Created winning handshake conversation for listing {listing_id}")
        
        # Notify via WebSocket if possible
        try:
            notification_manager = get_notification_manager()
            await notification_manager.send_to_user(winner_id, {
                "type": "AUCTION_WON",
                "listing_id": listing_id,
                "conversation_id": conversation_id,
                "item_title": item_title,
                "final_price": final_price
            })
        except Exception as e:
            logger.warning(f"Could not send auction won notification: {e}")
        
        return conversation_id
        
    except Exception as e:
        logger.error(f"Failed to create auction won conversation: {e}")
        return None


# ========== SERVE UPLOADED FILES ==========
@messages_router.get("/uploads/{filename}")
async def serve_message_attachment(filename: str):
    """Serve uploaded message attachment files"""
    from fastapi.responses import FileResponse
    
    file_path = Path("uploads/messages") / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine content type
    content_type = "application/octet-stream"
    if filename.lower().endswith(('.jpg', '.jpeg')):
        content_type = "image/jpeg"
    elif filename.lower().endswith('.png'):
        content_type = "image/png"
    elif filename.lower().endswith('.gif'):
        content_type = "image/gif"
    elif filename.lower().endswith('.webp'):
        content_type = "image/webp"
    elif filename.lower().endswith('.pdf'):
        content_type = "application/pdf"
    
    return FileResponse(
        path=str(file_path),
        media_type=content_type,
        filename=filename
    )
