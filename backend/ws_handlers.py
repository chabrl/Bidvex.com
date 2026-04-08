"""
BidVex WebSocket Endpoint Handlers.
Registered on the app instance (not on APIRouter) because FastAPI
WebSocket routes must be on the app directly for proper upgrade handling.
"""

from fastapi import WebSocket, WebSocketDisconnect, Query
from typing import Optional
from datetime import datetime, timezone
from shared import get_epoch_timestamp, get_server_timestamp
from models import Message
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


def register_ws_handlers(app, db, manager, message_manager, marketplace_ws=None):
    """Register all WebSocket endpoint handlers on the FastAPI app instance."""

    @app.websocket("/api/ws/marketplace")
    async def websocket_marketplace(websocket: WebSocket):
        """Global marketplace feed — broadcasts bid/time updates for all listings."""
        if not marketplace_ws:
            await websocket.close(code=4000, reason="Marketplace WS not initialized")
            return
        await marketplace_ws.connect(websocket)
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    data = json.loads(msg) if msg else {}
                    if data.get('type') == 'PING':
                        await websocket.send_json({'type': 'PONG', 'timestamp': datetime.now(timezone.utc).isoformat()})
                except asyncio.TimeoutError:
                    try:
                        await websocket.send_json({'type': 'HEARTBEAT', 'timestamp': datetime.now(timezone.utc).isoformat()})
                    except Exception:
                        break
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"Marketplace WS error: {e}")
        finally:
            marketplace_ws.disconnect(websocket)

    @app.websocket("/api/ws/listings/{listing_id}")
    async def websocket_endpoint(
        websocket: WebSocket,
        listing_id: str,
        user_id: Optional[str] = Query(default=None)
    ):
        await manager.connect(websocket, listing_id, user_id)
        try:
            await websocket.send_json({
                'type': 'CONNECTION_ESTABLISHED',
                'listing_id': listing_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'message': 'Real-time updates active'
            })
            listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
            if listing:
                highest_bid = await db.bids.find_one(
                    {"listing_id": listing_id}, {"_id": 0}, sort=[("amount", -1)]
                )
                highest_bidder_id = highest_bid.get('bidder_id') if highest_bid else None
                bid_status = 'LEADING' if user_id and user_id == highest_bidder_id else 'OUTBID' if highest_bid else 'NO_BIDS'
                auction_end_date = listing.get('auction_end_date')
                if auction_end_date and not isinstance(auction_end_date, str):
                    auction_end_date = auction_end_date.isoformat()
                auction_end_epoch = get_epoch_timestamp(listing.get('auction_end_date'))
                server_time_epoch = get_server_timestamp()
                now = datetime.now(timezone.utc)
                auction_active = True
                if auction_end_date:
                    try:
                        end_dt = datetime.fromisoformat(auction_end_date.replace('Z', '+00:00'))
                        auction_active = now < end_dt
                    except Exception:
                        pass
                await websocket.send_json({
                    'type': 'INITIAL_STATE',
                    'listing_id': listing_id,
                    'current_price': listing.get('current_price'),
                    'bid_count': listing.get('bid_count', 0),
                    'highest_bidder_id': highest_bidder_id,
                    'bid_status': bid_status,
                    'auction_end_date': auction_end_date,
                    'auction_end_epoch': auction_end_epoch,
                    'server_time_epoch': server_time_epoch,
                    'auction_active': auction_active,
                    'timestamp': now.isoformat()
                })
            while True:
                try:
                    message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    data = json.loads(message) if message else {}
                    if data.get('type') == 'PING':
                        await websocket.send_json({
                            'type': 'PONG',
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        })
                except asyncio.TimeoutError:
                    try:
                        await websocket.send_json({
                            'type': 'HEARTBEAT',
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        })
                    except Exception:
                        break
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"WebSocket error: {str(e)}")
        finally:
            manager.disconnect(websocket, listing_id, user_id)

    @app.websocket("/api/ws/messages/{user_id}")
    async def websocket_messages(websocket: WebSocket, user_id: str):
        await manager.connect_user(websocket, user_id)
        try:
            while True:
                await websocket.receive_text()
                await asyncio.sleep(0.1)
        except WebSocketDisconnect:
            manager.disconnect_user(websocket, user_id)

    @app.websocket("/api/ws/messaging/{conversation_id}")
    async def websocket_messaging(websocket: WebSocket, conversation_id: str, user_id: str = Query(None)):
        if not user_id:
            await websocket.close(code=4001, reason="User ID required")
            return
        conversation = await db.conversations.find_one({"id": conversation_id}, {"_id": 0})
        if not conversation:
            await websocket.close(code=4004, reason="Conversation not found")
            return
        if user_id not in conversation.get("participants", []):
            await websocket.close(code=4003, reason="Not authorized for this conversation")
            return

        await message_manager.connect(websocket, conversation_id, user_id)
        other_user_id = [p for p in conversation["participants"] if p != user_id][0]
        other_user = await db.users.find_one({"id": other_user_id}, {"_id": 0, "name": 1, "picture": 1, "id": 1})

        listing_info = None
        if conversation.get("listing_id"):
            listing = await db.multi_item_listings.find_one({"id": conversation["listing_id"]}, {"_id": 0, "id": 1, "title": 1, "lots": {"$slice": 1}})
            if not listing:
                listing = await db.listings.find_one({"id": conversation["listing_id"]}, {"_id": 0, "id": 1, "title": 1, "images": {"$slice": 1}, "current_price": 1})
            if listing:
                listing_info = {
                    "id": listing.get("id"),
                    "title": listing.get("title"),
                    "image": listing.get("images", [None])[0] if listing.get("images") else (listing.get("lots", [{}])[0].get("images", [None])[0] if listing.get("lots") else None),
                    "price": listing.get("current_price") or (listing.get("lots", [{}])[0].get("current_price") if listing.get("lots") else None),
                }

        try:
            await websocket.send_json({
                "type": "CONNECTION_ESTABLISHED",
                "conversation_id": conversation_id,
                "other_user": other_user,
                "other_user_online": message_manager.is_user_in_conversation(conversation_id, other_user_id),
                "listing_info": listing_info,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            await message_manager.send_to_conversation(conversation_id, {
                "type": "USER_STATUS", "user_id": user_id, "status": "online",
                "in_conversation": True, "timestamp": datetime.now(timezone.utc).isoformat()
            }, exclude_user=user_id)
        except Exception as e:
            logger.error(f"Error sending initial state: {str(e)}")
            return

        try:
            while True:
                try:
                    raw_message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    data = json.loads(raw_message)
                    message_manager.update_online_status(user_id)
                    msg_type = data.get("type")

                    if msg_type == "SEND_MESSAGE":
                        content = data.get("content", "").strip()
                        if not content:
                            await websocket.send_json({"type": "ERROR", "message": "Message content required"})
                            continue
                        msg = Message(conversation_id=conversation_id, sender_id=user_id,
                                      receiver_id=other_user_id, listing_id=conversation.get("listing_id"), content=content)
                        msg_dict = msg.model_dump()
                        msg_dict["created_at"] = msg_dict["created_at"].isoformat()
                        await db.messages.insert_one(msg_dict)
                        await db.conversations.update_one(
                            {"id": conversation_id},
                            {"$set": {"last_message": content[:100], "last_message_at": datetime.now(timezone.utc).isoformat()}}
                        )
                        await message_manager.send_to_conversation(conversation_id, {
                            "type": "NEW_MESSAGE", "message": msg_dict,
                            "sender": {"id": user_id, "name": (await db.users.find_one({"id": user_id}, {"name": 1})).get("name", "User")},
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }, exclude_user=user_id)
                        if not message_manager.is_user_in_conversation(conversation_id, other_user_id):
                            sender = await db.users.find_one({"id": user_id}, {"name": 1, "picture": 1})
                            await manager.send_to_user(other_user_id, {
                                "type": "new_message_notification", "conversation_id": conversation_id,
                                "sender_name": sender.get("name", "Someone"), "sender_picture": sender.get("picture"),
                                "preview": content[:50] + ("..." if len(content) > 50 else ""),
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })
                        await websocket.send_json({
                            "type": "MESSAGE_SENT", "message_id": msg_dict["id"],
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                        await message_manager.broadcast_typing_status(conversation_id, user_id, False)

                    elif msg_type == "TYPING_START":
                        await message_manager.broadcast_typing_status(conversation_id, user_id, True)
                    elif msg_type == "TYPING_STOP":
                        await message_manager.broadcast_typing_status(conversation_id, user_id, False)
                    elif msg_type == "MARK_READ":
                        message_ids = data.get("message_ids", [])
                        if message_ids:
                            await db.messages.update_many(
                                {"id": {"$in": message_ids}, "receiver_id": user_id},
                                {"$set": {"is_read": True, "read_at": datetime.now(timezone.utc).isoformat()}}
                            )
                            await message_manager.broadcast_read_receipt(conversation_id, user_id, message_ids)
                    elif msg_type == "PING":
                        await websocket.send_json({"type": "PONG", "timestamp": datetime.now(timezone.utc).isoformat()})

                except asyncio.TimeoutError:
                    try:
                        await websocket.send_json({"type": "HEARTBEAT", "timestamp": datetime.now(timezone.utc).isoformat()})
                    except Exception:
                        break
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"WebSocket messaging error: {str(e)}")
        finally:
            message_manager.disconnect(conversation_id, user_id)
            await message_manager.send_to_conversation(conversation_id, {
                "type": "USER_STATUS", "user_id": user_id, "status": "offline",
                "in_conversation": False, "timestamp": datetime.now(timezone.utc).isoformat()
            }, exclude_user=user_id)
