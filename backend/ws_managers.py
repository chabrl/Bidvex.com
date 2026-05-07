"""
BidVex WebSocket Connection Managers.
Handles real-time bidding updates and messaging.
"""

from fastapi import WebSocket
from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.user_connections: Dict[str, List[WebSocket]] = {}
        self.listing_viewers: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, listing_id: str, user_id: str = None):
        await websocket.accept()
        if listing_id not in self.active_connections:
            self.active_connections[listing_id] = []
        self.active_connections[listing_id].append(websocket)
        if user_id:
            if listing_id not in self.listing_viewers:
                self.listing_viewers[listing_id] = {}
            self.listing_viewers[listing_id][user_id] = websocket

    def disconnect(self, websocket: WebSocket, listing_id: str, user_id: str = None):
        if listing_id in self.active_connections:
            try:
                self.active_connections[listing_id].remove(websocket)
            except ValueError:
                pass
        if user_id and listing_id in self.listing_viewers:
            self.listing_viewers[listing_id].pop(user_id, None)

    async def broadcast(self, listing_id: str, message: dict):
        if listing_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[listing_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to connection: {str(e)}")
                    disconnected.append(connection)
            for conn in disconnected:
                try:
                    self.active_connections[listing_id].remove(conn)
                except ValueError:
                    pass

    async def broadcast_bid_update(self, listing_id: str, bid_data: dict, listing_data: dict):
        highest_bidder_id = bid_data.get('bidder_id')
        current_price = bid_data.get('amount')
        viewer_count = len(self.listing_viewers.get(listing_id, {}))
        connection_count = len(self.active_connections.get(listing_id, []))
        logger.info(f"Broadcasting bid update: listing_id={listing_id}, price={current_price}, viewers={viewer_count}, connections={connection_count}")
        sent_count = 0
        error_count = 0
        if listing_id in self.listing_viewers:
            for user_id, websocket in list(self.listing_viewers[listing_id].items()):
                try:
                    bid_status = 'LEADING' if user_id == highest_bidder_id else 'OUTBID'
                    message = {
                        'type': 'BID_UPDATE',
                        'listing_id': listing_id,
                        'current_price': current_price,
                        'highest_bidder_id': highest_bidder_id,
                        'bid_count': listing_data.get('bid_count', 0),
                        'bid_status': bid_status,
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'bid_data': bid_data,
                        'currency': listing_data.get('currency', 'CAD'),
                        # Anti-sniping extension sync fields
                        'time_extended': listing_data.get('time_extended', False),
                        'new_auction_end': listing_data.get('new_auction_end'),
                        'new_auction_end_epoch': listing_data.get('new_auction_end_epoch'),
                        'server_time_epoch': listing_data.get('server_time_epoch'),
                        'extension_reason': listing_data.get('extension_reason'),
                    }
                    await websocket.send_json(message)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Error sending to user {user_id}: {str(e)}")
                    error_count += 1
                    self.listing_viewers[listing_id].pop(user_id, None)
        # Fallback for non-tracked connections
        if listing_id in self.active_connections:
            tracked_sockets = set(self.listing_viewers.get(listing_id, {}).values())
            for websocket in list(self.active_connections[listing_id]):
                if websocket not in tracked_sockets:
                    try:
                        message = {
                            'type': 'BID_UPDATE',
                            'listing_id': listing_id,
                            'current_price': current_price,
                            'highest_bidder_id': highest_bidder_id,
                            'bid_count': listing_data.get('bid_count', 0),
                            'bid_status': 'UNKNOWN',
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'bid_data': bid_data,
                            'currency': listing_data.get('currency', 'CAD'),
                            'time_extended': listing_data.get('time_extended', False),
                            'new_auction_end': listing_data.get('new_auction_end'),
                            'new_auction_end_epoch': listing_data.get('new_auction_end_epoch'),
                            'server_time_epoch': listing_data.get('server_time_epoch'),
                        }
                        await websocket.send_json(message)
                        sent_count += 1
                    except Exception:
                        error_count += 1
        logger.info(f"Bid broadcast complete: sent={sent_count}, errors={error_count}")

    async def connect_user(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(websocket)

    def disconnect_user(self, websocket: WebSocket, user_id: str):
        if user_id in self.user_connections:
            try:
                self.user_connections[user_id].remove(websocket)
            except ValueError:
                pass

    async def send_to_user(self, user_id: str, message: dict):
        if user_id in self.user_connections:
            disconnected = []
            for conn in self.user_connections[user_id]:
                try:
                    await conn.send_json(message)
                except Exception:
                    disconnected.append(conn)
            for conn in disconnected:
                try:
                    self.user_connections[user_id].remove(conn)
                except ValueError:
                    pass

    def is_user_online(self, user_id: str) -> bool:
        """iter196 — used for offline-email gating."""
        return user_id in self.user_connections and len(self.user_connections[user_id]) > 0


class MessageConnectionManager:
    def __init__(self):
        self.conversation_rooms: Dict[str, Dict[str, WebSocket]] = {}
        self.user_active_convos: Dict[str, set] = {}
        self.user_online_status: Dict[str, datetime] = {}
        self.typing_status: Dict[str, Dict[str, bool]] = {}

    async def connect(self, websocket: WebSocket, conversation_id: str, user_id: str) -> bool:
        await websocket.accept()
        if conversation_id not in self.conversation_rooms:
            self.conversation_rooms[conversation_id] = {}
        self.conversation_rooms[conversation_id][user_id] = websocket
        if user_id not in self.user_active_convos:
            self.user_active_convos[user_id] = set()
        self.user_active_convos[user_id].add(conversation_id)
        self.user_online_status[user_id] = datetime.now(timezone.utc)
        if conversation_id not in self.typing_status:
            self.typing_status[conversation_id] = {}
        self.typing_status[conversation_id][user_id] = False
        return True

    def disconnect(self, conversation_id: str, user_id: str):
        if conversation_id in self.conversation_rooms:
            self.conversation_rooms[conversation_id].pop(user_id, None)
            if not self.conversation_rooms[conversation_id]:
                del self.conversation_rooms[conversation_id]
        if user_id in self.user_active_convos:
            self.user_active_convos[user_id].discard(conversation_id)
        if conversation_id in self.typing_status:
            self.typing_status[conversation_id].pop(user_id, None)

    async def send_to_conversation(self, conversation_id: str, message: dict, exclude_user: str = None):
        if conversation_id not in self.conversation_rooms:
            return
        disconnected = []
        for uid, websocket in self.conversation_rooms[conversation_id].items():
            if uid == exclude_user:
                continue
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(uid)
        for uid in disconnected:
            self.disconnect(conversation_id, uid)

    async def send_to_user_in_conversation(self, conversation_id: str, user_id: str, message: dict):
        if conversation_id in self.conversation_rooms:
            websocket = self.conversation_rooms[conversation_id].get(user_id)
            if websocket:
                try:
                    await websocket.send_json(message)
                except Exception:
                    self.disconnect(conversation_id, user_id)

    def is_user_online(self, user_id: str, timeout_seconds: int = 30) -> bool:
        if user_id not in self.user_online_status:
            return False
        return (datetime.now(timezone.utc) - self.user_online_status[user_id]).total_seconds() < timeout_seconds

    def is_user_in_conversation(self, conversation_id: str, user_id: str) -> bool:
        return (conversation_id in self.conversation_rooms and user_id in self.conversation_rooms[conversation_id])

    def update_online_status(self, user_id: str):
        self.user_online_status[user_id] = datetime.now(timezone.utc)

    async def broadcast_typing_status(self, conversation_id: str, user_id: str, is_typing: bool):
        self.typing_status.setdefault(conversation_id, {})[user_id] = is_typing
        await self.send_to_conversation(conversation_id, {
            "type": "TYPING_STATUS", "user_id": user_id, "is_typing": is_typing,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, exclude_user=user_id)

    async def broadcast_read_receipt(self, conversation_id: str, user_id: str, message_ids: List[str]):
        await self.send_to_conversation(conversation_id, {
            "type": "READ_RECEIPT", "reader_id": user_id, "message_ids": message_ids,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, exclude_user=user_id)

    def get_online_users_in_conversation(self, conversation_id: str) -> List[str]:
        if conversation_id not in self.conversation_rooms:
            return []
        return list(self.conversation_rooms[conversation_id].keys())


class MarketplaceConnectionManager:
    """Manages global marketplace WebSocket connections for real-time card updates."""

    def __init__(self):
        self.connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        try:
            self.connections.remove(websocket)
        except ValueError:
            pass

    async def broadcast(self, message: dict):
        disconnected = []
        for conn in self.connections:
            try:
                await conn.send_json(message)
            except Exception:
                disconnected.append(conn)
        for conn in disconnected:
            try:
                self.connections.remove(conn)
            except ValueError:
                pass
