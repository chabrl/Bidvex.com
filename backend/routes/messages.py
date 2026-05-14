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


# ---------------------------------------------------------------------------
# iter196 — Thread unlock gate
# ---------------------------------------------------------------------------

async def _can_open_thread(
    sender_id: str,
    receiver_id: str,
    listing_id: Optional[str],
    is_admin: bool = False,
) -> Optional[str]:
    """
    Returns None if the thread can be opened; otherwise an error code.
    Rules:
      • Admins always allowed.
      • Existing conversation? Allow replies (no re-check).
      • Vehicle listing: sender must be `winner_id` AND `unlock_paid_at` set,
        OR sender must be the seller and the buyer is `winner_id`.
      • Marketplace / Lots / Storage listings: auction must have ended AND
        sender must be the winner or the seller.
      • Listing-less ad-hoc messages (no listing_id) are allowed only for admins.
    """
    if is_admin:
        return None

    # Allow replies on existing conversations
    conv_id = "_".join(sorted([sender_id, receiver_id]))
    existing = await db.conversations.find_one({"id": conv_id}, {"_id": 0})
    if existing:
        return None

    if not listing_id:
        # New ad-hoc thread without a listing context — block per spec
        return "thread_requires_listing_context"

    # Vehicle listing
    vehicle = await db.vehicle_listings.find_one(
        {"id": listing_id},
        {"_id": 0, "winner_id": 1, "seller_id": 1, "unlock_paid_at": 1},
    )
    if vehicle:
        seller_user_id = None
        if vehicle.get("seller_id"):
            seller_doc = await db.vehicle_sellers.find_one(
                {"id": vehicle["seller_id"]}, {"_id": 0, "user_id": 1}
            )
            seller_user_id = seller_doc.get("user_id") if seller_doc else None
        winner_id = vehicle.get("winner_id")
        unlock_paid = bool(vehicle.get("unlock_paid_at"))

        # Winner can message seller only after paying unlock fee
        if sender_id == winner_id:
            if not unlock_paid:
                return "vehicle_unlock_fee_unpaid"
            if receiver_id != seller_user_id:
                return "must_message_seller"
            return None
        # Seller can message winner only after winner has paid
        if sender_id == seller_user_id:
            if not unlock_paid or receiver_id != winner_id:
                return "vehicle_unlock_fee_unpaid"
            return None
        return "not_party_to_transaction"

    # Marketplace / Lots / Storage / Multi-item — single common check: auction ended
    # + sender is winner or seller
    for coll in ("listings", "multi_item_listings", "storage_auctions"):
        doc = await db[coll].find_one(
            {"id": listing_id},
            {"_id": 0, "winner_id": 1, "seller_id": 1, "user_id": 1, "status": 1, "ended_at": 1, "end_time": 1},
        )
        if doc:
            now = datetime.now(timezone.utc)
            ended = doc.get("status") in ("ended", "sold", "completed")
            if not ended:
                # check end_time
                et = doc.get("end_time") or doc.get("ended_at")
                if isinstance(et, str):
                    try:
                        et = datetime.fromisoformat(et.replace("Z", "+00:00"))
                    except Exception:
                        et = None
                if et and et.tzinfo is None:
                    et = et.replace(tzinfo=timezone.utc)
                ended = bool(et and et < now)
            if not ended:
                return "auction_not_ended"

            seller_user_id = doc.get("seller_id") or doc.get("user_id")
            winner_id = doc.get("winner_id")
            allowed_pair = {seller_user_id, winner_id} - {None}
            if sender_id not in allowed_pair or receiver_id not in allowed_pair:
                return "not_party_to_transaction"
            return None

    # Listing not found — block defensively
    return "listing_not_found"


# ---------------------------------------------------------------------------
# Lazy db (set by server.py)
# ---------------------------------------------------------------------------

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
    # iter196 — gate thread creation
    is_admin = (current_user.role or "").lower() in ("admin", "superadmin") if hasattr(current_user, "role") else False
    gate_error = await _can_open_thread(current_user.id, msg.receiver_id, msg.listing_id, is_admin)
    if gate_error:
        ERROR_DETAILS = {
            "thread_requires_listing_context": {
                "code": "thread_requires_listing_context",
                "message_en": "Messages must be tied to a specific listing or auction.",
                "message_fr": "Les messages doivent être liés à une annonce ou enchère spécifique.",
            },
            "vehicle_unlock_fee_unpaid": {
                "code": "vehicle_unlock_fee_unpaid",
                "message_en": "The platform unlock fee must be paid before messaging the dealer.",
                "message_fr": "Les frais de plateforme doivent être payés avant de contacter le concessionnaire.",
            },
            "auction_not_ended": {
                "code": "auction_not_ended",
                "message_en": "Messaging is only available after the auction ends.",
                "message_fr": "La messagerie n'est disponible qu'après la fin de l'enchère.",
            },
            "not_party_to_transaction": {
                "code": "not_party_to_transaction",
                "message_en": "Only the winning bidder and the seller can open this thread.",
                "message_fr": "Seuls l'enchérisseur gagnant et le vendeur peuvent ouvrir ce fil.",
            },
            "must_message_seller": {
                "code": "must_message_seller",
                "message_en": "Vehicle messages must be sent to the seller of this listing.",
                "message_fr": "Les messages de véhicule doivent être envoyés au vendeur de cette annonce.",
            },
            "listing_not_found": {
                "code": "listing_not_found",
                "message_en": "Listing not found.",
                "message_fr": "Annonce introuvable.",
            },
        }
        raise HTTPException(status_code=403, detail=ERROR_DETAILS.get(gate_error, {"code": gate_error}))

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
    recipient_online = False
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

        recipient_online = message_manager.is_user_in_conversation(conversation_id, msg.receiver_id)
        if not recipient_online:
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

    # iter196 — Send email if recipient is offline (not in any websocket session)
    try:
        recipient_globally_online = ws_manager.is_user_online(msg.receiver_id) if ws_manager and hasattr(ws_manager, "is_user_online") else recipient_online
        if not recipient_globally_online:
            recipient = await db.users.find_one({"id": msg.receiver_id}, {"_id": 0, "email": 1, "name": 1, "preferred_language": 1})
            if recipient and recipient.get("email"):
                from services.email_notifications import send_new_message_email
                await send_new_message_email(
                    recipient=recipient,
                    sender_name=current_user.name,
                    preview=msg.content[:140],
                    listing_id=msg.listing_id,
                    conversation_id=conversation_id,
                )
    except Exception as exc:
        logger.warning(f"[iter196] new-message email failed: {exc}")

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
    winner_id: str,
    seller_id: str,
    # iter213 — accept BOTH legacy and new caller signatures.
    # Old internal helpers passed (item_title, final_price); the public
    # auction-close routes pass (listing_title, winning_amount, winner_info,
    # seller_info, lot_number). Keep all kwargs optional + map them.
    item_title: Optional[str] = None,
    final_price: Optional[float] = None,
    listing_title: Optional[str] = None,
    winning_amount: Optional[float] = None,
    winner_info: Optional[Dict[str, Any]] = None,
    seller_info: Optional[Dict[str, Any]] = None,
    lot_number: Optional[int] = None,
) -> Optional[str]:
    """Create the post-auction conversation between the winning bidder and
    the seller. Sends a system handshake message + bilingual EN+FR email
    to both parties + in-app notification + SMS (best-effort).

    iter213 — fixed signature mismatch so the function can be called with
    either the legacy `(item_title, final_price)` kwargs or the newer
    `(listing_title, winning_amount, winner_info, seller_info, lot_number)`
    kwargs the auction-close routes use. Also adds bilingual email
    notifications to both winner and seller with a deep link to the thread.
    """
    from services.sms_notification_service import get_sms_notification_service

    # Normalise the two competing signatures
    title = listing_title or item_title or "Item"
    if lot_number:
        title = f"{title} — Lot #{lot_number}"
    price = winning_amount if winning_amount is not None else (final_price or 0.0)

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
                "listing_title": title,
                "auction_winner_id": winner_id,
                "auction_seller_id": seller_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "last_message": "Auction won! Contact details shared.",
                "last_message_time": datetime.now(timezone.utc).isoformat()
            }
            await db.conversations.insert_one(conversation)

        # Resolve seller/winner docs (allow caller to pass them to skip the lookup)
        if seller_info:
            seller = seller_info
        else:
            seller = await db.users.find_one({"id": seller_id}, {"_id": 0}) or {}
        if winner_info:
            winner = winner_info
        else:
            winner = await db.users.find_one({"id": winner_id}, {"_id": 0}) or {}

        message_id = str(uuid.uuid4())
        system_message = {
            "id": message_id,
            "conversation_id": conversation_id,
            "sender_id": "system",
            "receiver_id": winner_id,
            "content": f"Congratulations! You have won the auction for {title}.",
            "message_type": "auction_won",
            "system_data": {
                "item_title": title,
                "final_price": price,
                "listing_id": listing_id,
                "seller_name": (seller or {}).get("name") if seller else "Seller",
                "seller_email": (seller or {}).get("email"),
                "seller_phone": (seller or {}).get("phone"),
                "lot_number": lot_number,
            },
            "is_read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        await db.messages.insert_one(system_message)

        logger.info(f"Created winning handshake conversation for listing {listing_id}")

        # iter213 — Bilingual EN+FR email to both parties
        try:
            from services.email_notifications import send_auction_thread_opened_email
            if (winner or {}).get("email"):
                await send_auction_thread_opened_email(
                    recipient=winner, role="winner",
                    counterparty=seller or {},
                    listing_title=title, listing_id=listing_id,
                    conversation_id=conversation_id,
                    winning_amount=price,
                )
            if (seller or {}).get("email"):
                await send_auction_thread_opened_email(
                    recipient=seller, role="seller",
                    counterparty=winner or {},
                    listing_title=title, listing_id=listing_id,
                    conversation_id=conversation_id,
                    winning_amount=price,
                )
        except Exception as email_err:
            logger.warning(f"Auction-thread email send failed (non-fatal): {email_err}")

        # WebSocket notification
        if ws_manager:
            try:
                await ws_manager.send_to_user(winner_id, {
                    "type": "AUCTION_WON",
                    "listing_id": listing_id,
                    "conversation_id": conversation_id,
                    "item_title": title,
                    "final_price": price
                })
                await ws_manager.send_to_user(seller_id, {
                    "type": "AUCTION_SOLD",
                    "listing_id": listing_id,
                    "conversation_id": conversation_id,
                    "item_title": title,
                    "final_price": price
                })
            except Exception as e:
                logger.warning(f"Could not send auction won notification: {e}")

        # SMS notifications
        try:
            sms_service = get_sms_notification_service(db)
            await sms_service.notify_auction_won(
                user_id=winner_id,
                listing_title=title,
                winning_amount=price,
                listing_id=listing_id
            )
            await sms_service.notify_seller_auction_sold(
                seller_id=seller_id,
                listing_title=title,
                sold_amount=price,
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

@messages_router.get("/admin/messages/threads")
async def admin_list_message_threads(
    limit: int = 50,
    offset: int = 0,
    listing_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """iter213 — Admin oversight: list all message threads (read-only).

    Returns a paginated list of conversation summaries with participant
    info, last message, last activity, and the linked listing (if any).
    Supports `?listing_id=<id>` for filtering threads tied to a given auction.
    """
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    query = {}
    if listing_id:
        query["listing_id"] = listing_id

    total = await db.conversations.count_documents(query)
    cursor = db.conversations.find(query, {"_id": 0}).sort("updated_at", -1).skip(offset).limit(limit)
    threads = await cursor.to_list(limit)

    # Enrich each thread with participant snapshots + message count
    out = []
    for t in threads:
        participants = t.get("participants", []) or []
        users_docs = []
        for uid in participants:
            doc = await db.users.find_one({"id": uid}, {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1})
            if doc:
                users_docs.append(doc)
        msg_count = await db.messages.count_documents({"conversation_id": t.get("id")})
        out.append({
            **t,
            "participants_detail": users_docs,
            "message_count": msg_count,
        })
    return {"total": total, "threads": out, "limit": limit, "offset": offset}


@messages_router.get("/admin/messages/thread/{conversation_id}")
async def admin_get_thread_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
):
    """iter213 — Admin oversight: fetch the full message log of one thread."""
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    conv = await db.conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msgs = await db.messages.find({"conversation_id": conversation_id}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    return {"conversation": conv, "messages": msgs}


@messages_router.get("/admin/messages/flagged")
async def admin_get_flagged_messages(current_user: User = Depends(get_current_user)):
    """Admin: Get all flagged messages."""
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    messages = await db.messages.find({"flagged": True}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return messages


@messages_router.delete("/admin/messages/{message_id}")
async def admin_delete_message(message_id: str, current_user: User = Depends(get_current_user)):
    """Admin: Delete a specific message."""
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    await db.messages.delete_one({"id": message_id})
    return {"message": "Message deleted"}


@messages_router.put("/admin/users/{user_id}/messaging")
async def admin_suspend_messaging(user_id: str, data: Dict[str, bool], current_user: User = Depends(get_current_user)):
    """Admin: Suspend or restore messaging for a user."""
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    messaging_suspended = data.get("suspended", False)
    await db.users.update_one({"id": user_id}, {"$set": {"messaging_suspended": messaging_suspended}})
    return {"message": f"Messaging {'suspended' if messaging_suspended else 'restored'}"}
