"""
Messaging Router
Handles internal chat, inbox, conversations, attachments, item sharing,
admin moderation, and the auction-won conversation helper.

Extracted from server.py during Phase 10 modularization.
Routes use explicit paths (no prefix) to preserve backward compatibility
with the frontend's existing API calls.
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse

from deps import User, get_current_user
from models.message_models import MessageCreate, Message

logger = logging.getLogger(__name__)

messages_router = APIRouter(tags=["Messaging"])

# Injected at startup from server.py
db = None
message_manager = None   # MessageConnectionManager (conversation rooms)
ws_manager = None         # ConnectionManager (global user notifications)


def set_messages_db(database):
    global db
    db = database


def set_message_managers(msg_manager, global_manager):
    """Inject the WebSocket connection managers from server.py."""
    global message_manager, ws_manager
    message_manager = msg_manager
    ws_manager = global_manager


# ---------------------------------------------------------------------------
# REST Endpoints — Messages
# ---------------------------------------------------------------------------

@messages_router.post("/messages")
async def send_message(msg: MessageCreate, current_user: User = Depends(get_current_user)):
    """Send a text message to another user."""
    conversation_id = "_".join(sorted([current_user.id, msg.receiver_id]))

    message = Message(
        conversation_id=conversation_id,
        sender_id=current_user.id,
        receiver_id=msg.receiver_id,
        listing_id=msg.listing_id,
        content=msg.content
    )

    msg_dict = message.model_dump()
    msg_dict["created_at"] = msg_dict["created_at"].isoformat()
    await db.messages.insert_one(msg_dict)

    update_fields = {
        "last_message": msg.content[:100],
        "last_message_at": datetime.now(timezone.utc).isoformat()
    }
    if msg.listing_id:
        update_fields["listing_id"] = msg.listing_id

    await db.conversations.update_one(
        {"id": conversation_id},
        {
            "$set": update_fields,
            "$setOnInsert": {
                "id": conversation_id,
                "participants": [current_user.id, msg.receiver_id],
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )

    sender_info = {"id": current_user.id, "name": current_user.name, "picture": current_user.picture}
    if message_manager:
        await message_manager.send_to_conversation(
            conversation_id,
            {
                "type": "NEW_MESSAGE",
                "message": msg_dict,
                "sender": sender_info,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            exclude_user=current_user.id
        )

        if not message_manager.is_user_in_conversation(conversation_id, msg.receiver_id):
            if ws_manager:
                await ws_manager.send_to_user(msg.receiver_id, {
                    "type": "new_message_notification",
                    "conversation_id": conversation_id,
                    "sender_name": current_user.name,
                    "sender_picture": current_user.picture,
                    "preview": msg.content[:50] + ("..." if len(msg.content) > 50 else ""),
                    "message": msg_dict,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

    return message


@messages_router.get("/messages/unread-count")
async def get_unread_message_count(current_user: User = Depends(get_current_user)):
    """Get total count of unread messages for current user."""
    count = await db.messages.count_documents({
        "receiver_id": current_user.id,
        "is_read": False
    })
    return {"unread_count": count}


@messages_router.get("/messages/{conversation_id}")
async def get_messages(conversation_id: str, current_user: User = Depends(get_current_user), limit: int = 50):
    """Get messages for a specific conversation."""
    messages = await db.messages.find(
        {"conversation_id": conversation_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)

    await db.messages.update_many(
        {"conversation_id": conversation_id, "receiver_id": current_user.id},
        {"$set": {"is_read": True}}
    )

    for msg in messages:
        if isinstance(msg.get("created_at"), str):
            msg["created_at"] = datetime.fromisoformat(msg["created_at"])

    return [Message(**msg) for msg in reversed(messages)]


@messages_router.get("/messages")
async def get_all_user_messages(
    current_user: User = Depends(get_current_user),
    listing_id: Optional[str] = None,
    limit: int = 50
):
    """Get all messages for current user, optionally filtered by listing_id."""
    query = {
        "$or": [
            {"sender_id": current_user.id},
            {"receiver_id": current_user.id}
        ]
    }

    if listing_id:
        query["listing_id"] = listing_id

    messages = await db.messages.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)

    await db.messages.update_many(
        {"receiver_id": current_user.id, "is_read": False},
        {"$set": {"is_read": True}}
    )


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

@messages_router.get("/conversations")
async def get_conversations(current_user: User = Depends(get_current_user)):
    """Get all conversations for the current user."""
    convos = await db.conversations.find(
        {"participants": current_user.id},
        {"_id": 0}
    ).sort("last_message_at", -1).to_list(100)

    for convo in convos:
        other_user_id = [p for p in convo["participants"] if p != current_user.id][0]
        user = await db.users.find_one({"id": other_user_id}, {"_id": 0, "name": 1, "picture": 1, "id": 1})
        convo["other_user"] = user

        unread = await db.messages.count_documents({
            "conversation_id": convo["id"],
            "receiver_id": current_user.id,
            "is_read": False
        })
        convo["unread_count"] = unread

    return convos


@messages_router.get("/conversations/{conversation_id}/online-status")
async def get_conversation_online_status(conversation_id: str, current_user: User = Depends(get_current_user)):
    """Get online status of users in a conversation."""
    conversation = await db.conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if current_user.id not in conversation.get("participants", []):
        raise HTTPException(status_code=403, detail="Not authorized")

    online_users = message_manager.get_online_users_in_conversation(conversation_id) if message_manager else []

    return {
        "conversation_id": conversation_id,
        "online_users": online_users,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ---------------------------------------------------------------------------
# Attachments & Item Sharing
# ---------------------------------------------------------------------------

@messages_router.post("/messages/attachment")
async def upload_message_attachment(
    file: UploadFile = File(...),
    receiver_id: str = Form(...),
    conversation_id: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    """Upload a file attachment in a message conversation (Max 10MB)."""
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be less than 10MB")

    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'application/pdf']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, GIF, WebP and PDF files are allowed")

    file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'bin'
    unique_filename = f"msg_{conversation_id}_{uuid.uuid4().hex[:8]}.{file_ext}"

    upload_dir = Path("uploads/messages")
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / unique_filename

    with open(file_path, "wb") as f:
        f.write(contents)

    base_url = os.environ.get("BACKEND_URL", os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001"))
    file_url = f"{base_url}/api/uploads/messages/{unique_filename}"

    message_id = str(uuid.uuid4())
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

    await db.conversations.update_one(
        {"id": conversation_id},
        {"$set": {
            "last_message": f"Attachment: {file.filename}",
            "last_message_time": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    # Fixed: was 'messaging_manager.send_message()' which didn't exist
    if message_manager:
        try:
            await message_manager.send_to_conversation(conversation_id, {
                "type": "NEW_MESSAGE",
                "message": message
            })
        except Exception as e:
            logger.warning(f"Could not send WebSocket notification: {e}")

    return {"status": "success", "message": message}


@messages_router.post("/messages/share-item-details")
async def share_item_details_in_chat(
    data: Dict[str, str],
    current_user: User = Depends(get_current_user)
):
    """Share item/listing details as a rich card in the chat."""
    conversation_id = data.get("conversation_id")
    listing_id = data.get("listing_id")

    if not conversation_id or not listing_id:
        raise HTTPException(status_code=400, detail="conversation_id and listing_id are required")

    convo = await db.conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if current_user.id not in convo.get("participants", []):
        raise HTTPException(status_code=403, detail="You are not part of this conversation")

    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.get("seller_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Only the seller can share item details")

    receiver_id = [p for p in convo.get("participants", []) if p != current_user.id][0]

    transaction = await db.payment_transactions.find_one({
        "listing_id": listing_id,
        "buyer_id": receiver_id
    }, {"_id": 0})
    payment_status = transaction.get("status", "pending") if transaction else "pending"

    message_id = str(uuid.uuid4())
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

    await db.conversations.update_one(
        {"id": conversation_id},
        {"$set": {
            "last_message": f"Shared item details: {listing.get('title')}",
            "last_message_time": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    # Fixed: was 'messaging_manager.send_message()' which didn't exist
    if message_manager:
        try:
            await message_manager.send_to_conversation(conversation_id, {
                "type": "NEW_MESSAGE",
                "message": message
            })
        except Exception as e:
            logger.warning(f"Could not send WebSocket notification: {e}")

    return {"status": "success", "message": message}


# ---------------------------------------------------------------------------
# File Serving (for uploaded message attachments)
# ---------------------------------------------------------------------------

@messages_router.get("/uploads/messages/{filename}")
async def serve_message_attachment(filename: str):
    """Serve uploaded message attachment files."""
    file_path = Path("uploads/messages") / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    content_type = "application/octet-stream"
    ext = filename.lower()
    if ext.endswith(('.jpg', '.jpeg')):
        content_type = "image/jpeg"
    elif ext.endswith('.png'):
        content_type = "image/png"
    elif ext.endswith('.gif'):
        content_type = "image/gif"
    elif ext.endswith('.webp'):
        content_type = "image/webp"
    elif ext.endswith('.pdf'):
        content_type = "application/pdf"

    return FileResponse(path=str(file_path), media_type=content_type, filename=filename)


# ---------------------------------------------------------------------------
# Helper: Auction-Won Conversation (called by routes/auctions.py)
# ---------------------------------------------------------------------------

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
    when an auction ends. Called from routes/auctions.py.

    Returns the conversation_id if successful, None otherwise.
    """
    from services.sms_notification_service import get_sms_notification_service

    try:
        existing = await db.conversations.find_one({
            "participants": {"$all": [seller_id, winner_id]},
            "listing_id": listing_id
        })

        if existing:
            conversation_id = existing["id"]
        else:
            conversation_id = str(uuid.uuid4())
            conversation = {
                "id": conversation_id,
                "participants": [seller_id, winner_id],
                "listing_id": listing_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "last_message": "Auction won! Contact details shared.",
                "last_message_time": datetime.now(timezone.utc).isoformat()
            }
            await db.conversations.insert_one(conversation)

        seller = await db.users.find_one({"id": seller_id}, {"_id": 0})

        message_id = str(uuid.uuid4())
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

        logger.info(f"Created winning handshake conversation for listing {listing_id}")

        # WebSocket notification
        if ws_manager:
            try:
                await ws_manager.send_to_user(winner_id, {
                    "type": "AUCTION_WON",
                    "listing_id": listing_id,
                    "conversation_id": conversation_id,
                    "item_title": item_title,
                    "final_price": final_price
                })
            except Exception as e:
                logger.warning(f"Could not send auction won notification: {e}")

        # SMS notifications
        try:
            sms_service = get_sms_notification_service(db)
            await sms_service.notify_auction_won(
                user_id=winner_id,
                listing_title=item_title,
                winning_amount=final_price,
                listing_id=listing_id
            )
            await sms_service.notify_seller_auction_sold(
                seller_id=seller_id,
                listing_title=item_title,
                sold_amount=final_price,
                listing_id=listing_id
            )
        except Exception as sms_error:
            logger.warning(f"SMS auction won notification failed: {sms_error}")

        return conversation_id

    except Exception as e:
        logger.error(f"Failed to create auction won conversation: {e}")
        return None


# ---------------------------------------------------------------------------
# Admin Endpoints
# ---------------------------------------------------------------------------

@messages_router.get("/admin/messages/flagged")
async def admin_get_flagged_messages(current_user: User = Depends(get_current_user)):
    """Admin: Get all flagged messages."""
    if not current_user.email.endswith("@bidvex.com"):
        raise HTTPException(status_code=403, detail="Admin access required")

    messages = await db.messages.find({"flagged": True}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return messages


@messages_router.delete("/admin/messages/{message_id}")
async def admin_delete_message(message_id: str, current_user: User = Depends(get_current_user)):
    """Admin: Delete a specific message."""
    if not current_user.email.endswith("@bidvex.com"):
        raise HTTPException(status_code=403, detail="Admin access required")

    await db.messages.delete_one({"id": message_id})
    return {"message": "Message deleted"}


@messages_router.put("/admin/users/{user_id}/messaging")
async def admin_suspend_messaging(user_id: str, data: Dict[str, bool], current_user: User = Depends(get_current_user)):
    """Admin: Suspend or restore messaging for a user."""
    if not current_user.email.endswith("@bidvex.com"):
        raise HTTPException(status_code=403, detail="Admin access required")

    messaging_suspended = data.get("suspended", False)
    await db.users.update_one({"id": user_id}, {"$set": {"messaging_suspended": messaging_suspended}})
    return {"message": f"Messaging {'suspended' if messaging_suspended else 'restored'}"}
