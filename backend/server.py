from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Header, status, WebSocket, WebSocketDisconnect, Query, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import json
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError
from pathlib import Path
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from services.email_service import get_email_service
import os
import logging
import uuid
import asyncio
import aiohttp

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
db_name = os.environ['DB_NAME']
jwt_secret = os.environ['JWT_SECRET']
stripe_api_key = os.environ['STRIPE_API_KEY']
google_maps_key = os.environ.get('GOOGLE_MAPS_API_KEY', '')

client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

import stripe
stripe.api_key = stripe_api_key

# Fix for MongoDB ObjectId serialization in FastAPI
from bson.objectid import ObjectId

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== EMAIL TEMPLATE SETTINGS (SendGrid Template IDs) ==========
# All 40+ email templates stored in database for admin management
DEFAULT_EMAIL_TEMPLATES = {
    # Authentication
    "auth_password_reset_en": "d-dbfba723dd5e4895a579b462b19c56fb",
    "auth_password_reset_fr": "d-9084b4478e024056a9fa5207fdfc91e6",
    "auth_password_changed_en": "d-1e018cb66df54ee58616f9abd0720b0f",
    "auth_password_changed_fr": "d-16ad9371e1c54f2996f4ff453dfc2b82",
    "auth_email_verification_en": "d-79352dd5a50849c7bb4cbe93e726051f",
    "auth_email_verification_fr": "d-48d6d49961ab439f89d55b890bc84b8a",
    "auth_welcome_en": "d-db7d296ad54247138f3f210a1fb52e0a",
    "auth_welcome_fr": "d-256f3801670441808730c4cfb259d9a2",
    "auth_two_factor_en": "d-7fe6f17a934f491ca91aa36534be85e2",
    "auth_two_factor_fr": "d-ec1e531f92bc4d01bf24dc47620cabed",
    "auth_login_alert_en": "d-2cbb18036b9e44e4ba67ac3ee614e339",
    "auth_login_alert_fr": "d-2e3509d0a8c3480e83cd0d6b6ffc8c25",
    # Admin
    "admin_account_suspended_en": "d-cf2d8fb5bad74d4ab00b85236a93755d",
    "admin_account_suspended_fr": "d-89596fbe221f4740aa29cff3d09d6754",
    "admin_report_received_en": "d-539a4d89254f42baa38de4f139e7a36b",
    "admin_report_received_fr": "d-1e6b72f9301c49949b9a5cb21f0a39d5",
    # Communication
    "comm_announcement_en": "d-877f77c6623b4ed3879e4a7fcab2f8a5",
    "comm_announcement_fr": "d-b1fd6b2e096d47bb95c96fc9ca93af68",
    "comm_support_ack_en": "d-5a4bdee8c66041ba8d44ba0d7fc0244a",
    "comm_support_ack_fr": "d-7ecc0e3ab5c24c8283416a0e1ef4c9eb",
    "comm_platform_updates_en": "d-268de17d00514f3bb674e688d414b157",
    "comm_platform_updates_fr": "d-3dc15879450146dd9e1d48e59dc8cccc",
    # Financial
    "fin_invoice_issued_en": "d-d25445886edb4cc08cc8107b07cb343f",
    "fin_invoice_issued_fr": "d-780daa32909e438aad5ee459cb21703a",
    "fin_payment_receipt_en": "d-5f88411aa2584e63afccbbe6603b3b3a",
    "fin_payment_receipt_fr": "d-110c93dfaea74c439488cdbe89985bf3",
    "fin_payout_sent_en": "d-36b5f93ff1064b8c815253aa60c02829",
    "fin_payout_sent_fr": "d-73eae4ffc4e9404f9aa931493a4f2724",
    # Seller
    "seller_new_bid_en": "d-da5049e2aac143aa937c4dd113d9fb96",
    "seller_new_bid_fr": "d-5e45290634c648d5aa818a733a94f13d",
    "seller_listing_approved_en": "d-e65e2943cc6d4b0b968fb0f877357fc0",
    "seller_listing_approved_fr": "d-2d34d8977ef84acaad852ddf73cf8fb7",
    "seller_listing_rejected_en": "d-57976d80ab25467cad32db22cd11d06b",
    "seller_listing_rejected_fr": "d-168a20ae972845658e166bc442904136",
    # Auction
    "auction_announcement_en": "d-e525a2ab091a42049f75fb9d102b9cde",
    "auction_announcement_fr": "d-7a20775199774c5b84e0c3c12c1721a6",
    "auction_reminder_en": "d-7ae5b7a394494823b16e71a1029e1e6e",
    "auction_reminder_fr": "d-8c5efdf9cd2449a7b288bc8d3be54885",
    "auction_results_en": "d-4c519ffa806f41729c07b5c9feca09ab",
    "auction_results_fr": "d-284252b173364ddab13854da54c70a87",
    # Bidding
    "bid_outbid_en": "d-89c95108533249aaa1659e258f11dd90",
    "bid_outbid_fr": "d-94110d612e1243a58fc28c99872cfce6",
    "bid_confirmed_en": "d-fde06627d9dc4b79a250123604efb39c",
    "bid_confirmed_fr": "d-e1fec1eab388405cb172f71c7b6e7879",
    "bid_winning_en": "d-27a3e1edafe24fa09437ab929eeab070",
    "bid_winning_fr": "d-a790684646d0430b91686923b46bf697",
    # Affiliate Program
    "affiliate_monthly_earnings_en": "d-bacce34b0273477f8e7e4df61b737512",
    "affiliate_monthly_earnings_fr": "d-7e4e67d882ad490fac384ab166e7f89b",
    "affiliate_commission_earned_en": "d-60618f4cb6d54a579fe4cc82052ea41d",
    "affiliate_commission_earned_fr": "d-df3d97fe87b34060b5b6dee14977efcd",
    "affiliate_referral_notification_en": "d-da95ceff24c54d39b15a29e56d804ee9",
    "affiliate_referral_notification_fr": "d-32a08f1a11a7441186944747602cfd53",
}

# Email template categories for admin UI
EMAIL_TEMPLATE_CATEGORIES = {
    "authentication": {
        "name": "Authentication",
        "description": "User authentication emails (login, password, verification)",
        "icon": "🔐",
        "keys": ["auth_password_reset", "auth_password_changed", "auth_email_verification", 
                 "auth_welcome", "auth_two_factor", "auth_login_alert"]
    },
    "financial": {
        "name": "Financial",
        "description": "Invoices, receipts, and payout notifications",
        "icon": "💰",
        "keys": ["fin_invoice_issued", "fin_payment_receipt", "fin_payout_sent"]
    },
    "bidding": {
        "name": "Bidding & Auction",
        "description": "Bid confirmations, outbid alerts, and auction results",
        "icon": "🔨",
        "keys": ["bid_outbid", "bid_confirmed", "bid_winning", "auction_announcement",
                 "auction_reminder", "auction_results"]
    },
    "seller": {
        "name": "Seller Notifications",
        "description": "Seller-specific emails for bids and listing status",
        "icon": "🏪",
        "keys": ["seller_new_bid", "seller_listing_approved", "seller_listing_rejected"]
    },
    "communication": {
        "name": "Communication & Admin",
        "description": "Announcements, support acknowledgments, and admin alerts",
        "icon": "📢",
        "keys": ["comm_announcement", "comm_support_ack", "comm_platform_updates",
                 "admin_account_suspended", "admin_report_received"]
    },
    "affiliate": {
        "name": "Affiliate Program",
        "description": "Commission and referral notifications",
        "icon": "🤝",
        "keys": ["affiliate_monthly_earnings", "affiliate_commission_earned", 
                 "affiliate_referral_notification"]
    }
}

async def get_email_templates():
    """Fetch email templates from database, or return defaults if not set."""
    templates = await db.email_settings.find_one({"id": "email_templates"}, {"_id": 0})
    if not templates:
        # Initialize with defaults
        templates = {
            "id": "email_templates",
            "templates": DEFAULT_EMAIL_TEMPLATES,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": "system"
        }
        await db.email_settings.insert_one(templates)
    return templates

async def get_email_template_id(template_key: str, language: str = "en") -> str:
    """
    Get a specific email template ID based on key and language.
    Falls back to English if language-specific template not found.
    """
    templates = await get_email_templates()
    template_dict = templates.get("templates", {})
    
    # Try language-specific key first
    lang_key = f"{template_key}_{language}"
    if lang_key in template_dict:
        return template_dict[lang_key]
    
    # Fall back to English
    en_key = f"{template_key}_en"
    if en_key in template_dict:
        return template_dict[en_key]
    
    # Return default placeholder if not found
    return "d-default-template-id"

# ========== MARKETPLACE SETTINGS (Global Configuration) ==========
# These settings are stored in the database and can be changed by admins
DEFAULT_MARKETPLACE_SETTINGS = {
    "id": "marketplace_settings",
    "allow_all_users_multi_lot": True,  # If False, only business accounts can create multi-lot auctions
    "require_approval_new_sellers": False,  # If True, first-time sellers need admin approval
    "max_active_auctions_per_user": 20,
    "max_lots_per_auction": 50,
    "minimum_bid_increment": 1.0,
    "enable_anti_sniping": True,
    "anti_sniping_window_minutes": 2,
    "enable_buy_now": True,
    "updated_at": None,
    "updated_by": None
}

async def get_marketplace_settings():
    """Fetch marketplace settings from database, or return defaults if not set."""
    settings = await db.settings.find_one({"id": "marketplace_settings"}, {"_id": 0})
    if not settings:
        # Initialize with defaults
        settings = {**DEFAULT_MARKETPLACE_SETTINGS, "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.settings.insert_one(settings)
    return settings

# ========== TIMEZONE-SAFE TIMESTAMP HELPER ==========
def get_epoch_timestamp(dt) -> int:
    """
    Convert datetime to Unix epoch timestamp (seconds since 1970-01-01 UTC).
    This is immune to timezone interpretation issues on the frontend.
    """
    if dt is None:
        return None
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        # Assume UTC if no timezone
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())

def get_server_timestamp() -> int:
    """Get current server time as Unix epoch timestamp."""
    return int(datetime.now(timezone.utc).timestamp())

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.user_connections: Dict[str, List[WebSocket]] = {}
        # Track user IDs per listing for status updates
        self.listing_viewers: Dict[str, Dict[str, WebSocket]] = {}  # {listing_id: {user_id: websocket}}

    async def connect(self, websocket: WebSocket, listing_id: str, user_id: str = None):
        await websocket.accept()
        if listing_id not in self.active_connections:
            self.active_connections[listing_id] = []
        self.active_connections[listing_id].append(websocket)
        
        # Track user viewing this listing
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
        
        # Remove user from listing viewers
        if user_id and listing_id in self.listing_viewers:
            self.listing_viewers[listing_id].pop(user_id, None)

    async def broadcast(self, listing_id: str, message: dict):
        """Broadcast message to all connections viewing a specific listing"""
        if listing_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[listing_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to connection: {str(e)}")
                    disconnected.append(connection)
            
            # Clean up disconnected websockets
            for conn in disconnected:
                try:
                    self.active_connections[listing_id].remove(conn)
                except ValueError:
                    pass

    async def broadcast_bid_update(self, listing_id: str, bid_data: dict, listing_data: dict):
        """
        Enhanced broadcast with personalized status updates for each user.
        Sends LEADING/OUTBID status based on user_id.
        """
        highest_bidder_id = bid_data.get('bidder_id')
        current_price = bid_data.get('amount')
        
        # Log broadcast attempt
        viewer_count = len(self.listing_viewers.get(listing_id, {}))
        connection_count = len(self.active_connections.get(listing_id, []))
        logger.info(f"📡 Broadcasting bid update: listing_id={listing_id}, price={current_price}, viewers={viewer_count}, connections={connection_count}")
        
        sent_count = 0
        error_count = 0
        
        if listing_id in self.listing_viewers:
            for user_id, websocket in list(self.listing_viewers[listing_id].items()):
                try:
                    # Determine bid status for this user
                    bid_status = 'LEADING' if user_id == highest_bidder_id else 'OUTBID'
                    
                    # Personalized message for each user
                    message = {
                        'type': 'BID_UPDATE',
                        'listing_id': listing_id,
                        'current_price': current_price,
                        'highest_bidder_id': highest_bidder_id,
                        'bid_count': listing_data.get('bid_count', 0),
                        'bid_status': bid_status,  # Personalized status
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'bid_data': bid_data,
                        # Anti-sniping time extension data
                        'time_extended': listing_data.get('time_extended', False),
                        'new_auction_end': listing_data.get('new_auction_end'),
                        'extension_reason': listing_data.get('extension_reason')
                    }
                    
                    await websocket.send_json(message)
                    sent_count += 1
                    logger.info(f"✅ Sent bid update to user {user_id}: status={bid_status}")
                except Exception as e:
                    error_count += 1
                    logger.error(f"❌ Error sending bid update to user {user_id}: {str(e)}")
                    # Clean up dead connection
                    try:
                        self.listing_viewers[listing_id].pop(user_id, None)
                    except:
                        pass
        
        # Also broadcast to anonymous viewers (non-logged-in)
        if listing_id in self.active_connections:
            for connection in list(self.active_connections[listing_id]):
                if connection not in [ws for ws in self.listing_viewers.get(listing_id, {}).values()]:
                    try:
                        message = {
                            'type': 'BID_UPDATE',
                            'listing_id': listing_id,
                            'current_price': current_price,
                            'highest_bidder_id': highest_bidder_id,
                            'bid_count': listing_data.get('bid_count', 0),
                            'bid_status': 'VIEWER',  # Not bidding
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'bid_data': bid_data,
                            # Anti-sniping time extension data
                            'time_extended': listing_data.get('time_extended', False),
                            'new_auction_end': listing_data.get('new_auction_end'),
                            'extension_reason': listing_data.get('extension_reason')
                        }
                        await connection.send_json(message)
                        sent_count += 1
                    except Exception as e:
                        error_count += 1
                        # Clean up dead connection
                        try:
                            self.active_connections[listing_id].remove(connection)
                        except:
                            pass
        
        logger.info(f"📊 Broadcast complete: sent={sent_count}, errors={error_count}")

    async def send_to_user(self, user_id: str, message: dict):
        """Send message to specific user (for notifications, messages, etc.)"""
        if user_id in self.user_connections:
            for connection in self.user_connections[user_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass
    
    async def connect_user(self, websocket: WebSocket, user_id: str):
        """Connect user for personal notifications"""
        await websocket.accept()
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(websocket)
    
    def disconnect_user(self, websocket: WebSocket, user_id: str):
        """Disconnect user from personal notifications"""
        if user_id in self.user_connections:
            try:
                self.user_connections[user_id].remove(websocket)
            except ValueError:
                pass

manager = ConnectionManager()

# ========== MESSAGING CONNECTION MANAGER ==========
class MessageConnectionManager:
    """
    WebSocket connection manager for real-time messaging.
    Handles conversation rooms, typing indicators, and read receipts.
    """
    def __init__(self):
        # {conversation_id: {user_id: WebSocket}}
        self.conversation_rooms: Dict[str, Dict[str, WebSocket]] = {}
        # {user_id: set of conversation_ids} - tracks which convos user is actively in
        self.user_active_convos: Dict[str, set] = {}
        # {user_id: timestamp} - last seen online
        self.user_online_status: Dict[str, datetime] = {}
        # {conversation_id: {user_id: bool}} - typing status
        self.typing_status: Dict[str, Dict[str, bool]] = {}
    
    async def connect(self, websocket: WebSocket, conversation_id: str, user_id: str) -> bool:
        """Connect user to a conversation room. Returns False if user not authorized."""
        await websocket.accept()
        
        # Track connection
        if conversation_id not in self.conversation_rooms:
            self.conversation_rooms[conversation_id] = {}
        self.conversation_rooms[conversation_id][user_id] = websocket
        
        # Track user's active conversations
        if user_id not in self.user_active_convos:
            self.user_active_convos[user_id] = set()
        self.user_active_convos[user_id].add(conversation_id)
        
        # Update online status
        self.user_online_status[user_id] = datetime.now(timezone.utc)
        
        # Initialize typing status
        if conversation_id not in self.typing_status:
            self.typing_status[conversation_id] = {}
        self.typing_status[conversation_id][user_id] = False
        
        logger.info(f"💬 User {user_id} connected to conversation {conversation_id}")
        return True
    
    def disconnect(self, conversation_id: str, user_id: str):
        """Disconnect user from conversation room."""
        if conversation_id in self.conversation_rooms:
            self.conversation_rooms[conversation_id].pop(user_id, None)
            if not self.conversation_rooms[conversation_id]:
                del self.conversation_rooms[conversation_id]
        
        if user_id in self.user_active_convos:
            self.user_active_convos[user_id].discard(conversation_id)
        
        # Clear typing status
        if conversation_id in self.typing_status:
            self.typing_status[conversation_id].pop(user_id, None)
        
        logger.info(f"💬 User {user_id} disconnected from conversation {conversation_id}")
    
    async def send_to_conversation(self, conversation_id: str, message: dict, exclude_user: str = None):
        """Send message to all users in a conversation except the excluded one."""
        if conversation_id not in self.conversation_rooms:
            return
        
        disconnected = []
        for user_id, websocket in self.conversation_rooms[conversation_id].items():
            if user_id == exclude_user:
                continue
            try:
                await websocket.send_json(message)
                logger.info(f"📤 Sent message to user {user_id} in conversation {conversation_id}")
            except Exception as e:
                logger.error(f"❌ Error sending to user {user_id}: {str(e)}")
                disconnected.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected:
            self.disconnect(conversation_id, user_id)
    
    async def send_to_user_in_conversation(self, conversation_id: str, user_id: str, message: dict):
        """Send message to a specific user in a conversation."""
        if conversation_id in self.conversation_rooms:
            websocket = self.conversation_rooms[conversation_id].get(user_id)
            if websocket:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"❌ Error sending to user {user_id}: {str(e)}")
                    self.disconnect(conversation_id, user_id)
    
    def is_user_online(self, user_id: str, timeout_seconds: int = 30) -> bool:
        """Check if user is currently online (active within timeout)."""
        if user_id not in self.user_online_status:
            return False
        last_seen = self.user_online_status[user_id]
        return (datetime.now(timezone.utc) - last_seen).total_seconds() < timeout_seconds
    
    def is_user_in_conversation(self, conversation_id: str, user_id: str) -> bool:
        """Check if user is currently viewing a specific conversation."""
        return (conversation_id in self.conversation_rooms and 
                user_id in self.conversation_rooms[conversation_id])
    
    def update_online_status(self, user_id: str):
        """Update user's online status timestamp."""
        self.user_online_status[user_id] = datetime.now(timezone.utc)
    
    async def broadcast_typing_status(self, conversation_id: str, user_id: str, is_typing: bool):
        """Broadcast typing indicator to other users in conversation."""
        self.typing_status.setdefault(conversation_id, {})[user_id] = is_typing
        
        await self.send_to_conversation(
            conversation_id,
            {
                "type": "TYPING_STATUS",
                "user_id": user_id,
                "is_typing": is_typing,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            exclude_user=user_id
        )
    
    async def broadcast_read_receipt(self, conversation_id: str, user_id: str, message_ids: List[str]):
        """Broadcast read receipt to other users."""
        await self.send_to_conversation(
            conversation_id,
            {
                "type": "READ_RECEIPT",
                "reader_id": user_id,
                "message_ids": message_ids,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            exclude_user=user_id
        )
    
    def get_online_users_in_conversation(self, conversation_id: str) -> List[str]:
        """Get list of online users in a conversation."""
        if conversation_id not in self.conversation_rooms:
            return []
        return list(self.conversation_rooms[conversation_id].keys())

message_manager = MessageConnectionManager()

# Scheduled job to transition upcoming auctions to active
async def transition_upcoming_auctions():
    """
    Background task that runs every 5 minutes to check for upcoming auctions
    whose start date has passed and transitions them to 'active' status.
    """
    try:
        now = datetime.now(timezone.utc)
        
        # Find all upcoming auctions where start date has passed
        upcoming_auctions = await db.multi_item_listings.find({
            "status": "upcoming",
            "auction_start_date": {"$lte": now.isoformat()}
        }).to_list(100)
        
        transition_count = 0
        for auction in upcoming_auctions:
            # Update status to active
            await db.multi_item_listings.update_one(
                {"id": auction["id"]},
                {"$set": {"status": "active"}}
            )
            transition_count += 1
            logger.info(f"Transitioned auction {auction['id']} from upcoming to active")
        
        if transition_count > 0:
            logger.info(f"✅ Transitioned {transition_count} upcoming auction(s) to active")
        
    except Exception as e:
        logger.error(f"❌ Error in transition_upcoming_auctions: {str(e)}")

# Initialize APScheduler
scheduler = AsyncIOScheduler()
scheduler.add_job(
    transition_upcoming_auctions,
    trigger=IntervalTrigger(minutes=5),
    id='transition_upcoming_auctions',
    name='Transition upcoming auctions to active',
    replace_existing=True
)

# Add job to process ended auctions every minute
async def run_process_ended_auctions():
    """Wrapper to run the async auction end processor"""
    from routes.auctions import process_ended_auctions
    await process_ended_auctions()

scheduler.add_job(
    run_process_ended_auctions,
    trigger=IntervalTrigger(minutes=1),
    id='process_ended_auctions',
    name='Process ended auctions and create handshakes',
    replace_existing=True
)

# Start scheduler on app startup
@app.on_event("startup")
async def start_scheduler():
    scheduler.start()
    logger.info("🚀 APScheduler started - checking auctions every minute, transitions every 5 minutes")

@app.on_event("shutdown")
async def shutdown_scheduler():
    scheduler.shutdown()
    logger.info("🛑 APScheduler shut down")

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    account_type: str
    phone: str
    address: Optional[str] = None
    company_name: Optional[str] = None
    tax_number: Optional[str] = None
    bank_details: Optional[Dict[str, str]] = None

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    name: str
    account_type: str
    role: Optional[str] = None  # admin, superadmin, or None for regular users
    phone: str
    phone_verified: bool = False
    address: Optional[str] = None
    company_name: Optional[str] = None
    tax_number: Optional[str] = None
    bank_details: Optional[Dict[str, str]] = None
    picture: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    language: str = "en"  # Kept for backward compatibility
    preferred_language: str = "en"  # en or fr
    preferred_currency: str = "CAD"  # CAD or USD
    enforced_currency: Optional[str] = None  # Currency enforced by location
    currency_locked: bool = False  # Whether currency can be changed
    location_confidence_score: Optional[int] = None  # 0-100
    affiliate_code: Optional[str] = None
    billing_address: Optional[str] = None  # For invoicing
    # Premium subscription fields
    subscription_tier: str = "free"  # free, premium, vip
    subscription_status: str = "active"  # active, cancelled, expired
    subscription_start_date: Optional[datetime] = None
    subscription_end_date: Optional[datetime] = None
    monster_bids_used: Dict[str, int] = Field(default_factory=dict)  # {auction_id: count}
    # Seller profile fields
    bio: Optional[str] = None  # Seller bio (max 500 chars)
    bio_fr: Optional[str] = None  # French bio (max 500 chars)
    privacy_settings: Dict[str, bool] = Field(default_factory=lambda: {
        "show_email": True,
        "show_phone": True,
        "show_address": True
    })

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User

class ListingCreate(BaseModel):
    title: str
    description: str
    category: str
    condition: str
    starting_price: float
    buy_now_price: Optional[float] = None
    images: List[str] = []
    location: str
    city: str
    region: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    auction_end_date: datetime
    shipping_info: Optional[Dict[str, Any]] = None  # {available, methods, rates, delivery_time}
    visit_availability: Optional[Dict[str, Any]] = None  # {offered, dates, instructions}

class AuctionRating(BaseModel):
    """
    Model for storing seller/auctioneer ratings.
    One rating per auction per buyer.
    """
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    auction_id: str  # Can be Listing ID or MultiItemListing ID
    auction_type: str  # "single" or "multi"
    rater_user_id: str  # Buyer who is rating
    target_user_id: str  # Seller/auctioneer being rated
    rating: int = Field(ge=1, le=5)  # 1-5 stars
    comment: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Listing(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    seller_id: str
    title: str
    description: str
    category: str
    condition: str
    starting_price: float
    current_price: float
    buy_now_price: Optional[float] = None
    images: List[str] = []
    location: str
    city: str
    region: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    auction_end_date: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "active"
    bid_count: int = 0
    is_promoted: bool = False
    views: int = 0
    shipping_info: Optional[Dict[str, Any]] = None  # {available, methods, rates, delivery_time}
    visit_availability: Optional[Dict[str, Any]] = None  # {offered, dates, instructions}

class BidCreate(BaseModel):
    listing_id: str
    amount: float

class BuyNowPurchase(BaseModel):
    auction_id: str  # Multi-item listing ID
    lot_number: int  # Which lot/item to buy
    quantity: int = 1  # How many units to purchase
    
class BuyNowTransaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    auction_id: str
    lot_number: int
    buyer_id: str
    quantity_purchased: int
    price_per_unit: float
    total_amount: float
    transaction_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payment_status: str = "pending"  # pending, completed, failed
    payment_method: Optional[str] = None
    bid_type: str = "normal"  # normal, monster, auto

class Bid(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    listing_id: str
    bidder_id: str
    amount: float
    bid_type: str = "normal"  # normal, monster, auto
    auto_bid_max: Optional[float] = None  # For auto-bid bot
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Wishlist(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    auction_id: str
    lot_id: Optional[str] = None  # Specific lot or entire auction
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AutoBid(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    listing_id: str
    max_bid: float
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Category(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name_en: str
    name_fr: str
    icon: str

class SessionCreate(BaseModel):
    session_id: str

class MessageCreate(BaseModel):
    receiver_id: str
    content: str
    listing_id: Optional[str] = None

class Message(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    sender_id: str
    receiver_id: str
    listing_id: Optional[str] = None
    content: str
    is_read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Lot(BaseModel):
    lot_number: int
    title: str
    description: str
    quantity: int
    starting_price: float
    current_price: float
    condition: str
    images: List[str] = []
    lot_end_time: Optional[datetime] = None  # Staggered end time (1 min per lot)
    pricing_mode: str = "multiplied"  # "fixed" or "multiplied" - how quantity affects final price
    extension_count: int = 0  # Number of 3-min extensions applied (max 3)
    # Buy Now functionality
    buy_now_price: Optional[float] = None  # Fixed "Buy Now" price per unit
    buy_now_enabled: bool = False  # Toggle Buy Now availability
    available_quantity: int = None  # Current available quantity (decrements on Buy Now)
    sold_quantity: int = 0  # Quantity sold via Buy Now
    lot_status: str = "active"  # active, partially_sold, sold_out, auction_ended
    # Bid tracking
    bid_count: int = 0
    highest_bidder_id: Optional[str] = None
    # Promotion
    is_promoted: bool = False  # Seller-paid promotion
    promotion_tier: Optional[str] = None  # "premium", "standard", "basic"
    impressions: int = 0  # Number of times viewed in search
    clicks: int = 0  # Number of times clicked

class MultiItemListingCreate(BaseModel):
    title: str
    description: str
    category: str
    location: str
    city: str
    region: str
    auction_end_date: datetime
    auction_start_date: Optional[datetime] = None
    lots: List[Lot]
    currency: Optional[str] = None  # CAD or USD, auto-detected if not provided
    documents: Optional[Dict[str, Any]] = None  # {terms_conditions, important_info, catalogue}
    shipping_info: Optional[Dict[str, Any]] = None  # {available, methods, rates, delivery_time}
    visit_availability: Optional[Dict[str, Any]] = None  # {offered, dates, instructions}
    auction_terms_en: Optional[str] = None  # English auction terms (rich text HTML)
    auction_terms_fr: Optional[str] = None  # French auction terms (rich text HTML)

class MultiItemListing(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    seller_id: str
    title: str
    description: str
    category: str
    location: str
    city: str
    region: str
    auction_end_date: datetime
    auction_start_date: Optional[datetime] = None
    lots: List[Lot]
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_lots: int = 0
    views: int = 0
    wishlist_count: int = 0  # Total users who wishlisted this auction
    currency: str = "CAD"  # CAD or USD
    increment_option: str = "tiered"  # tiered or simplified
    is_featured: bool = False  # VIP auto-promotion
    promotion_expiry: Optional[datetime] = None  # 7-day promotion for VIP
    # Seller promotion (paid feature)
    is_promoted: bool = False  # Seller-paid promotion flag
    promotion_tier: Optional[str] = None  # "premium" ($50), "standard" ($25), "basic" ($10)
    promotion_start: Optional[datetime] = None
    promotion_end: Optional[datetime] = None
    # Analytics for promoted listings
    total_impressions: int = 0  # Total views in search results
    total_clicks: int = 0  # Total clicks to detail page
    # Invoice configuration
    premium_percentage: float = 5.0  # Buyer's premium (5%)
    commission_rate: float = 0.0      # Seller commission (0% - no commission charged)
    tax_rate_gst: float = 5.0         # GST (5%) - CAD only
    tax_rate_qst: float = 9.975       # QST (9.975%) - CAD only
    payment_deadline: Optional[datetime] = None
    pickup_locations: Optional[List[Dict[str, Any]]] = None  # [{address, hours, deadline}]
    # Payment tracking fields
    payment_status: str = "pending"   # pending, paid, partial
    payment_date: Optional[datetime] = None
    # Documents (base64 encoded, max 10MB each)
    documents: Optional[Dict[str, Any]] = None  # {terms_conditions, important_info, catalogue}
    # Shipping information
    shipping_info: Optional[Dict[str, Any]] = None  # {available, methods, rates, delivery_time}
    # Visit availability
    visit_availability: Optional[Dict[str, Any]] = None  # {offered, dates, instructions}
    payment_method: Optional[str] = None  # e-transfer, bank transfer, cash, etc.
    payment_proof_url: Optional[str] = None  # URL to payment receipt/proof
    # Auction terms (rich text HTML content)
    auction_terms_en: Optional[str] = None  # English auction terms
    auction_terms_fr: Optional[str] = None  # French auction terms

class PaymentTransaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    user_id: Optional[str] = None
    listing_id: Optional[str] = None
    amount: float
    currency: str
    payment_status: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PaddleNumber(BaseModel):
    """Paddle number assignment for buyer in specific auction"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    auction_id: str
    user_id: str
    paddle_number: int
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Invoice(BaseModel):
    """Invoice/document generation tracking"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    invoice_number: str  # BV-2025-AUC123-0001
    invoice_type: str    # 'lots_won', 'payment_letter', 'seller_statement', etc.
    user_id: str
    auction_id: str
    pdf_path: str
    generated_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "generated"  # 'generated', 'sent', 'viewed', 'paid'
    # Payment tracking
    payment_status: str = "pending"  # pending, paid, partial
    payment_date: Optional[datetime] = None
    payment_method: Optional[str] = None
    payment_proof_url: Optional[str] = None
    # Email tracking
    email_sent: bool = False
    sent_timestamp: Optional[datetime] = None
    recipient_email: Optional[str] = None

class PaymentMethodCreate(BaseModel):
    payment_method_id: str

class PaymentMethodResponse(BaseModel):
    id: str
    user_id: str
    stripe_payment_method_id: str
    card_brand: str
    last4: str
    exp_month: int
    exp_year: int
    is_verified: bool
    is_default: bool

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    company_name: Optional[str] = None
    tax_number: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    language: Optional[str] = None
    picture: Optional[str] = None

class LocationSearchParams(BaseModel):
    latitude: float
    longitude: float
    radius_km: float = 50.0
    category: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, jwt_secret, algorithm="HS256")

# Increment logic helper functions
def get_minimum_increment_tiered(current_bid: float) -> float:
    """
    Tiered increment schedule (Option A):
    $0-$99.99 → $5
    $100-$499.99 → $10
    $500-$999.99 → $25
    $1,000-$4,999.99 → $50
    $5,000-$9,999.99 → $100
    $10,000-$49,999.99 → $250
    $50,000-$99,999.99 → $500
    $100,000+ → $1,000
    """
    if current_bid < 100:
        return 5
    elif current_bid < 500:
        return 10
    elif current_bid < 1000:
        return 25
    elif current_bid < 5000:
        return 50
    elif current_bid < 10000:
        return 100
    elif current_bid < 50000:
        return 250
    elif current_bid < 100000:
        return 500
    else:
        return 1000

def get_minimum_increment_simplified(current_bid: float) -> float:
    """
    Simplified increment schedule (Option B):
    $0-$100 → $1
    $100-$1,000 → $5
    $1,000-$10,000 → $25
    $10,000+ → $100
    """
    if current_bid <= 100:
        return 1
    elif current_bid <= 1000:
        return 5
    elif current_bid <= 10000:
        return 25
    else:
        return 100

def get_minimum_increment(auction: dict, current_bid: float) -> float:
    """Get minimum increment based on auction's increment_option"""
    increment_option = auction.get("increment_option", "tiered")
    if increment_option == "simplified":
        return get_minimum_increment_simplified(current_bid)
    else:
        return get_minimum_increment_tiered(current_bid)

async def get_current_user(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> User:
    token = None
    if "session_token" in request.cookies:
        token = request.cookies["session_token"]
    elif credentials:
        token = credentials.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
        if not user_doc:
            raise HTTPException(status_code=401, detail="User not found")
        return User(**user_doc)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate, request: Request):
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_pwd = hash_password(user_data.password)
    
    # Get geolocation and enforce currency
    from geolocation_service import geolocation_service
    client_ip = get_client_ip(request)
    
    ip_location = await geolocation_service.get_location_from_ip(client_ip)
    confidence_data = geolocation_service.calculate_location_confidence(
        ip_location=ip_location,
        billing_country=None,  # Not available at registration
        shipping_country=None
    )
    enforcement_data = geolocation_service.determine_enforced_currency(
        ip_location=ip_location,
        confidence_data=confidence_data
    )
    
    # Create user with enforced currency
    user = User(
        email=user_data.email, name=user_data.name, account_type=user_data.account_type,
        phone=user_data.phone, address=user_data.address, company_name=user_data.company_name,
        tax_number=user_data.tax_number, bank_details=user_data.bank_details,
        preferred_language="en",
        preferred_currency=enforcement_data['enforced_currency'],
        enforced_currency=enforcement_data['enforced_currency'],
        currency_locked=enforcement_data['currency_locked'],
        location_confidence_score=confidence_data['confidence_score']
    )
    user_dict = user.model_dump()
    user_dict["password"] = hashed_pwd
    user_dict["created_at"] = user_dict["created_at"].isoformat()
    await db.users.insert_one(user_dict)
    
    # Audit log
    await db.currency_audit_logs.insert_one({
        "user_id": user.id,
        "action": "registration",
        "ip_address": client_ip,
        "ip_location": ip_location,
        "confidence_data": confidence_data,
        "enforcement_data": enforcement_data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    token = create_access_token({"sub": user.id})
    return TokenResponse(access_token=token, user=user)

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user_doc = await db.users.find_one({"email": credentials.email})
    if not user_doc or not verify_password(credentials.password, user_doc["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user_doc.pop("password")
    user_doc.pop("_id")
    if isinstance(user_doc.get("created_at"), str):
        user_doc["created_at"] = datetime.fromisoformat(user_doc["created_at"])
    user = User(**user_doc)
    token = create_access_token({"sub": user.id})
    return TokenResponse(access_token=token, user=user)

@api_router.post("/auth/session")
async def process_session(session_data: SessionCreate):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_data.session_id}
        ) as response:
            if response.status != 200:
                raise HTTPException(status_code=400, detail="Invalid session")
            data = await response.json()
            existing_user = await db.users.find_one({"email": data["email"]})
            if not existing_user:
                user = User(
                    email=data["email"], name=data["name"], picture=data.get("picture"),
                    account_type="personal", phone="", phone_verified=False
                )
                user_dict = user.model_dump()
                user_dict["created_at"] = user_dict["created_at"].isoformat()
                await db.users.insert_one(user_dict)
                user_id = user.id
            else:
                user_id = existing_user["id"]
            session_token = create_access_token({"sub": user_id})
            session_doc = {
                "user_id": user_id, "session_token": data["session_token"],
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.sessions.insert_one(session_doc)
            return {"session_token": session_token}

@api_router.post("/auth/logout")
async def logout(current_user: User = Depends(get_current_user)):
    await db.sessions.delete_many({"user_id": current_user.id})
    return {"message": "Logged out successfully"}

@api_router.get("/auth/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

# Password Reset Models
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class PasswordResetToken(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    token: str
    expires_at: datetime
    used: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

@api_router.post("/auth/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    """
    Initiate password reset process.
    Sends reset email if user exists (doesn't reveal if email exists for security).
    """
    try:
        # Find user by email
        user_doc = await db.users.find_one({"email": request.email}, {"_id": 0})
        
        if user_doc:
            # Generate secure reset token
            reset_token = str(uuid.uuid4())
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)  # 1 hour expiry
            
            # Store reset token in database
            token_doc = {
                "id": str(uuid.uuid4()),
                "user_id": user_doc["id"],
                "token": reset_token,
                "expires_at": expires_at.isoformat(),
                "used": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.password_reset_tokens.insert_one(token_doc)
            
            # Send password reset email using SendGrid
            email_service = get_email_service()
            
            if email_service.is_configured():
                from config.email_templates import send_password_reset_email, EmailDataBuilder
                
                try:
                    # Build email data for logging
                    email_data = EmailDataBuilder.password_reset_email(user_doc, reset_token)
                    logger.info(f"Sending password reset email with data: {email_data}")
                    
                    result = await send_password_reset_email(
                        email_service,
                        user=user_doc,
                        reset_token=reset_token,
                        language=user_doc.get('preferred_language', 'en')
                    )
                    
                    if result['success']:
                        logger.info(f"Password reset email sent to {request.email}, message_id: {result.get('message_id')}")
                    else:
                        logger.error(f"Failed to send password reset email: {result.get('error')}")
                        # Don't fail the request, just log the error
                        
                except Exception as e:
                    logger.exception(f"Error sending password reset email: {str(e)}")
                    # Don't reveal email service errors to user
            else:
                logger.warning("Email service not configured - password reset email not sent")
        
        # Always return success to prevent email enumeration
        return {
            "message": "If an account with that email exists, a password reset link has been sent.",
            "success": True
        }
        
    except Exception as e:
        logger.exception(f"Error in forgot_password: {str(e)}")
        # Return generic message to prevent information leakage
        return {
            "message": "If an account with that email exists, a password reset link has been sent.",
            "success": True
        }

@api_router.post("/auth/reset-password")
async def reset_password(request: ResetPasswordRequest):
    """
    Reset password using valid token.
    """
    try:
        # Find the token
        token_doc = await db.password_reset_tokens.find_one(
            {"token": request.token, "used": False},
            {"_id": 0}
        )
        
        if not token_doc:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")
        
        # Check if token is expired
        expires_at = datetime.fromisoformat(token_doc["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(status_code=400, detail="Reset token has expired")
        
        # Get user
        user_doc = await db.users.find_one(
            {"id": token_doc["user_id"]},
            {"_id": 0}
        )
        
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Validate new password
        if len(request.new_password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
        
        # Hash new password
        hashed_password = pwd_context.hash(request.new_password)
        
        # Update user password
        await db.users.update_one(
            {"id": user_doc["id"]},
            {"$set": {"password": hashed_password}}
        )
        
        # Mark token as used
        await db.password_reset_tokens.update_one(
            {"token": request.token},
            {"$set": {"used": True}}
        )
        
        # Invalidate all existing sessions for security
        await db.sessions.delete_many({"user_id": user_doc["id"]})
        
        # Send password changed confirmation email
        email_service = get_email_service()
        
        if email_service.is_configured():
            try:
                from config.email_templates import EmailTemplates, EmailDataBuilder
                
                result = await email_service.send_email(
                    to=user_doc["email"],
                    template_id=EmailTemplates.PASSWORD_CHANGED,
                    dynamic_data=EmailDataBuilder.password_changed_email(user_doc),
                    language=user_doc.get('preferred_language', 'en')
                )
                
                if result['success']:
                    logger.info(f"Password changed confirmation sent to {user_doc['email']}")
                else:
                    logger.error(f"Failed to send password changed email: {result.get('error')}")
                    
            except Exception as e:
                logger.exception(f"Error sending password changed email: {str(e)}")
        
        logger.info(f"Password reset successful for user {user_doc['id']}")
        
        return {
            "message": "Password reset successful. Please log in with your new password.",
            "success": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in reset_password: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while resetting password")

@api_router.get("/auth/verify-reset-token/{token}")
async def verify_reset_token(token: str):
    """
    Verify if a reset token is valid and not expired.
    Used by frontend to check token before showing password reset form.
    """
    try:
        token_doc = await db.password_reset_tokens.find_one(
            {"token": token, "used": False},
            {"_id": 0}
        )
        
        if not token_doc:
            return {"valid": False, "message": "Invalid or already used token"}
        
        # Check if expired
        expires_at = datetime.fromisoformat(token_doc["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            return {"valid": False, "message": "Token has expired"}
        
        # Calculate time remaining
        time_remaining = expires_at - datetime.now(timezone.utc)
        minutes_remaining = int(time_remaining.total_seconds() / 60)
        
        return {
            "valid": True,
            "message": "Token is valid",
            "expires_in_minutes": minutes_remaining
        }
        
    except Exception as e:
        logger.exception(f"Error verifying reset token: {str(e)}")
        return {"valid": False, "message": "Error verifying token"}

@api_router.get("/users/{user_id}", response_model=User)
async def get_user(user_id: str):
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    if isinstance(user_doc.get("created_at"), str):
        user_doc["created_at"] = datetime.fromisoformat(user_doc["created_at"])
    return User(**user_doc)

@api_router.get("/users/{user_id}/profile-summary")
async def get_user_profile_summary(user_id: str):
    """
    Get auctioneer profile summary for display on auction cards.
    Returns name, location, profile image, and seller statistics.
    """
    try:
        # Get user data
        user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Calculate seller statistics
        total_single_auctions = await db.listings.count_documents({"seller_id": user_id})
        total_lots_auctions = await db.multi_item_listings.count_documents({"seller_id": user_id})
        total_auctions = total_single_auctions + total_lots_auctions
        
        # Calculate completed auctions
        completed_single = await db.listings.count_documents({
            "seller_id": user_id,
            "status": {"$in": ["sold", "ended"]}
        })
        completed_lots = await db.multi_item_listings.count_documents({
            "seller_id": user_id,
            "status": {"$in": ["ended", "completed"]}
        })
        completed_auctions = completed_single + completed_lots
        
        # Build profile summary
        profile_summary = {
            "user_id": user_id,
            "name": user_doc.get("name", "Anonymous"),
            "picture": user_doc.get("picture"),
            "company_name": user_doc.get("company_name"),
            "account_type": user_doc.get("account_type", "personal"),
            "city": user_doc.get("address", "").split(",")[0] if user_doc.get("address") else None,
            "subscription_tier": user_doc.get("subscription_tier", "free"),
            "stats": {
                "total_auctions": total_auctions,
                "completed_auctions": completed_auctions,
                "member_since": user_doc.get("created_at")
            }
        }
        
        return profile_summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user profile summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch profile summary")

# ============= RATING ENDPOINTS =============

@api_router.post("/ratings")
async def create_rating(
    rating_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """
    Create a rating for a seller/auctioneer after participating in an auction.
    One rating per auction per buyer.
    """
    try:
        required_fields = ["auction_id", "auction_type", "target_user_id", "rating"]
        for field in required_fields:
            if field not in rating_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Validate rating value
        if not (1 <= rating_data["rating"] <= 5):
            raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
        
        # Validate auction type
        if rating_data["auction_type"] not in ["single", "multi"]:
            raise HTTPException(status_code=400, detail="Auction type must be 'single' or 'multi'")
        
        # Check if user has already rated this auction
        existing_rating = await db.ratings.find_one({
            "auction_id": rating_data["auction_id"],
            "rater_user_id": current_user.id
        })
        
        if existing_rating:
            raise HTTPException(status_code=400, detail="You have already rated this auction")
        
        # Verify the auction exists and user participated
        if rating_data["auction_type"] == "single":
            auction = await db.listings.find_one({"id": rating_data["auction_id"]})
            if not auction:
                raise HTTPException(status_code=404, detail="Auction not found")
            
            # Check if user has bids on this auction
            user_bid = await db.bids.find_one({
                "listing_id": rating_data["auction_id"],
                "bidder_id": current_user.id
            })
            if not user_bid:
                raise HTTPException(status_code=403, detail="You must participate in the auction to rate it")
        else:
            auction = await db.multi_item_listings.find_one({"id": rating_data["auction_id"]})
            if not auction:
                raise HTTPException(status_code=404, detail="Auction not found")
            
            # Check if user has bids on any lot in this auction
            user_bid = await db.bids.find_one({
                "multi_item_listing_id": rating_data["auction_id"],
                "bidder_id": current_user.id
            })
            if not user_bid:
                raise HTTPException(status_code=403, detail="You must participate in the auction to rate it")
        
        # Prevent self-rating
        if current_user.id == rating_data["target_user_id"]:
            raise HTTPException(status_code=400, detail="You cannot rate yourself")
        
        # Create rating
        rating = AuctionRating(
            auction_id=rating_data["auction_id"],
            auction_type=rating_data["auction_type"],
            rater_user_id=current_user.id,
            target_user_id=rating_data["target_user_id"],
            rating=rating_data["rating"],
            comment=rating_data.get("comment")
        )
        
        rating_dict = rating.model_dump()
        rating_dict["timestamp"] = rating_dict["timestamp"].isoformat()
        rating_dict["created_at"] = rating_dict["created_at"].isoformat()
        
        await db.ratings.insert_one(rating_dict)
        
        return {"message": "Rating submitted successfully", "rating": rating_dict}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating rating: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create rating")

@api_router.get("/users/{user_id}/ratings")
async def get_user_ratings(user_id: str):
    """
    Get aggregated ratings for a specific seller/auctioneer.
    Returns average rating, count, and recent ratings.
    """
    try:
        # Get all ratings for this user
        ratings_cursor = db.ratings.find({"target_user_id": user_id})
        ratings = await ratings_cursor.to_list(length=None)
        
        if not ratings:
            return {
                "user_id": user_id,
                "average_rating": 0,
                "total_ratings": 0,
                "ratings_breakdown": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
                "recent_ratings": []
            }
        
        # Calculate average
        total_rating = sum(r["rating"] for r in ratings)
        average_rating = round(total_rating / len(ratings), 2)
        
        # Ratings breakdown
        ratings_breakdown = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
        for r in ratings:
            ratings_breakdown[str(r["rating"])] += 1
        
        # Get recent ratings (last 10)
        recent_ratings = sorted(ratings, key=lambda x: x.get("timestamp", ""), reverse=True)[:10]
        
        # Remove sensitive IDs from recent ratings
        for r in recent_ratings:
            r.pop("_id", None)
            r.pop("rater_user_id", None)
        
        return {
            "user_id": user_id,
            "average_rating": average_rating,
            "total_ratings": len(ratings),
            "ratings_breakdown": ratings_breakdown,
            "recent_ratings": recent_ratings
        }
        
    except Exception as e:
        logger.error(f"Error fetching user ratings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch ratings")

# ============= SELLER PROFILE ENDPOINTS =============

@api_router.get("/sellers/{seller_id}")
async def get_seller_profile(
    seller_id: str,
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """
    Get seller profile with privacy-aware contact information.
    Contact details only visible to authenticated users based on seller's privacy settings.
    """
    try:
        # Check if user is authenticated (optional)
        current_user = None
        token = None
        if "session_token" in request.cookies:
            token = request.cookies["session_token"]
        elif credentials:
            token = credentials.credentials
        
        if token:
            try:
                payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
                user_id = payload.get("sub")
                if user_id:
                    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
                    if user_doc:
                        if isinstance(user_doc.get("created_at"), str):
                            user_doc["created_at"] = datetime.fromisoformat(user_doc["created_at"])
                        current_user = User(**user_doc)
            except (JWTError, Exception):
                pass  # Invalid token, proceed as unauthenticated
        
        # Get seller data
        seller_doc = await db.users.find_one({"id": seller_id}, {"_id": 0, "password": 0})
        if not seller_doc:
            raise HTTPException(status_code=404, detail="Seller not found")
        
        # Get seller ratings
        ratings_cursor = db.ratings.find({"target_user_id": seller_id})
        ratings = await ratings_cursor.to_list(length=None)
        
        average_rating = 0
        total_ratings = len(ratings)
        if ratings:
            total_rating = sum(r["rating"] for r in ratings)
            average_rating = round(total_rating / len(ratings), 2)
        
        # Count active listings
        single_listings_count = await db.listings.count_documents({
            "seller_id": seller_id,
            "status": "active"
        })
        multi_listings_count = await db.multi_item_listings.count_documents({
            "seller_id": seller_id,
            "status": {"$in": ["active", "upcoming"]}
        })
        total_active_listings = single_listings_count + multi_listings_count
        
        # Build base profile
        profile = {
            "id": seller_id,
            "name": seller_doc.get("name"),
            "company_name": seller_doc.get("company_name"),
            "account_type": seller_doc.get("account_type"),
            "picture": seller_doc.get("picture"),
            "bio": seller_doc.get("bio"),
            "bio_fr": seller_doc.get("bio_fr"),
            "subscription_tier": seller_doc.get("subscription_tier", "free"),
            "member_since": seller_doc.get("created_at"),
            "average_rating": average_rating,
            "total_ratings": total_ratings,
            "total_active_listings": total_active_listings
        }
        
        # Apply privacy settings (only for authenticated users)
        privacy_settings = seller_doc.get("privacy_settings", {
            "show_email": True,
            "show_phone": True,
            "show_address": True
        })
        
        if current_user:
            # Show contact info based on privacy settings
            if privacy_settings.get("show_email", True):
                profile["email"] = seller_doc.get("email")
            if privacy_settings.get("show_phone", True):
                profile["phone"] = seller_doc.get("phone")
            if privacy_settings.get("show_address", True):
                profile["address"] = seller_doc.get("address")
        
        return profile
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching seller profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch seller profile")

@api_router.get("/sellers/{seller_id}/listings")
async def get_seller_listings(seller_id: str, limit: int = 20, skip: int = 0):
    """
    Get active listings for a specific seller (both single-item and multi-lot auctions).
    """
    try:
        # Get single-item listings
        single_listings = await db.listings.find(
            {"seller_id": seller_id, "status": "active"},
            {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        
        # Get multi-item listings
        multi_listings = await db.multi_item_listings.find(
            {"seller_id": seller_id, "status": {"$in": ["active", "upcoming"]}},
            {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        
        # Format datetime fields
        for listing in single_listings:
            if isinstance(listing.get("created_at"), str):
                listing["created_at"] = datetime.fromisoformat(listing["created_at"])
            if isinstance(listing.get("auction_end_date"), str):
                listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])
        
        for listing in multi_listings:
            if isinstance(listing.get("created_at"), str):
                listing["created_at"] = datetime.fromisoformat(listing["created_at"])
            if isinstance(listing.get("auction_end_date"), str):
                listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])
            if isinstance(listing.get("auction_start_date"), str):
                listing["auction_start_date"] = datetime.fromisoformat(listing["auction_start_date"])
        
        return {
            "single_listings": single_listings,
            "multi_listings": multi_listings,
            "total": len(single_listings) + len(multi_listings)
        }
        
    except Exception as e:
        logger.error(f"Error fetching seller listings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch seller listings")

@api_router.put("/users/me")
async def update_profile(updates: Dict[str, Any], current_user: User = Depends(get_current_user)):
    allowed_fields = ["name", "phone", "address", "company_name", "tax_number", "bank_details", "language", "picture", "preferred_language", "preferred_currency", "subscription_tier", "bio", "bio_fr", "privacy_settings"]
    update_data = {k: v for k, v in updates.items() if k in allowed_fields}
    
    # Validate bio length
    if "bio" in update_data and update_data["bio"] and len(update_data["bio"]) > 500:
        raise HTTPException(status_code=400, detail="Bio must be 500 characters or less")
    if "bio_fr" in update_data and update_data["bio_fr"] and len(update_data["bio_fr"]) > 500:
        raise HTTPException(status_code=400, detail="French bio must be 500 characters or less")
    
    # Validate privacy settings
    if "privacy_settings" in update_data:
        if not isinstance(update_data["privacy_settings"], dict):
            raise HTTPException(status_code=400, detail="Privacy settings must be an object")
        valid_keys = {"show_email", "show_phone", "show_address"}
        if not all(k in valid_keys for k in update_data["privacy_settings"].keys()):
            raise HTTPException(status_code=400, detail="Invalid privacy setting keys")
    
    # Validate language
    if "preferred_language" in update_data and update_data["preferred_language"] not in ["en", "fr"]:
        raise HTTPException(status_code=400, detail="Language must be 'en' or 'fr'")
    
    # Validate currency - check if locked
    if "preferred_currency" in update_data:
        if update_data["preferred_currency"] not in ["CAD", "USD"]:
            raise HTTPException(status_code=400, detail="Currency must be 'CAD' or 'USD'")
        
        # Check if currency is locked
        if current_user.currency_locked and update_data["preferred_currency"] != current_user.enforced_currency:
            raise HTTPException(
                status_code=403, 
                detail={
                    "error": "currency_locked",
                    "message": "Currency is determined by your location to comply with local tax rules. If you're traveling or have moved, please submit an appeal.",
                    "enforced_currency": current_user.enforced_currency,
                    "appeal_link": "/api/currency-appeal"
                }
            )
    
    # Validate subscription tier
    if "subscription_tier" in update_data:
        if update_data["subscription_tier"] not in ["free", "premium", "vip"]:
            raise HTTPException(status_code=400, detail="Subscription tier must be 'free', 'premium', or 'vip'")
    
    if update_data:
        await db.users.update_one({"id": current_user.id}, {"$set": update_data})
    return {"message": "Profile updated successfully"}

@api_router.post("/listings", response_model=Listing)
async def create_listing(listing_data: ListingCreate, current_user: User = Depends(get_current_user)):
    listing = Listing(
        seller_id=current_user.id, title=listing_data.title, description=listing_data.description,
        category=listing_data.category, condition=listing_data.condition,
        starting_price=listing_data.starting_price, current_price=listing_data.starting_price,
        buy_now_price=listing_data.buy_now_price, images=listing_data.images,
        location=listing_data.location, city=listing_data.city, region=listing_data.region,
        latitude=listing_data.latitude, longitude=listing_data.longitude,
        auction_end_date=listing_data.auction_end_date,
        shipping_info=listing_data.shipping_info,
        visit_availability=listing_data.visit_availability
    )
    listing_dict = listing.model_dump()
    listing_dict["auction_end_date"] = listing_dict["auction_end_date"].isoformat()
    listing_dict["created_at"] = listing_dict["created_at"].isoformat()
    await db.listings.insert_one(listing_dict)
    return listing

@api_router.get("/listings", response_model=List[Listing])
async def get_listings(
    category: Optional[str] = None, city: Optional[str] = None, region: Optional[str] = None,
    condition: Optional[str] = None, min_price: Optional[float] = None, max_price: Optional[float] = None,
    search: Optional[str] = None, sort: str = "created_at", limit: int = 50, skip: int = 0
):
    query = {"status": "active"}
    if category:
        query["category"] = category
    if city:
        query["city"] = city
    if region:
        query["region"] = region
    if condition:
        query["condition"] = condition
    if min_price is not None:
        query["current_price"] = {"$gte": min_price}
    if max_price is not None:
        if "current_price" in query:
            query["current_price"]["$lte"] = max_price
        else:
            query["current_price"] = {"$lte": max_price}
    if search:
        query["$or"] = [{"title": {"$regex": search, "$options": "i"}}, {"description": {"$regex": search, "$options": "i"}}]
    sort_order = -1 if sort.startswith("-") else 1
    sort_field = sort.lstrip("-")
    listings = await db.listings.find(query, {"_id": 0}).sort(sort_field, sort_order).skip(skip).limit(limit).to_list(limit)
    for listing in listings:
        if isinstance(listing.get("created_at"), str):
            listing["created_at"] = datetime.fromisoformat(listing["created_at"])
        if isinstance(listing.get("auction_end_date"), str):
            listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])
    return [Listing(**listing) for listing in listings]

@api_router.get("/listings/{listing_id}", response_model=Listing)
async def get_listing(listing_id: str):
    listing_doc = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing_doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    await db.listings.update_one({"id": listing_id}, {"$inc": {"views": 1}})
    if isinstance(listing_doc.get("created_at"), str):
        listing_doc["created_at"] = datetime.fromisoformat(listing_doc["created_at"])
    if isinstance(listing_doc.get("auction_end_date"), str):
        listing_doc["auction_end_date"] = datetime.fromisoformat(listing_doc["auction_end_date"])
    return Listing(**listing_doc)

@api_router.put("/listings/{listing_id}", response_model=Listing)
async def update_listing(listing_id: str, updates: Dict[str, Any], current_user: User = Depends(get_current_user)):
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["seller_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    allowed_fields = ["title", "description", "category", "condition", "images", "location", "city", "region", "status"]
    update_data = {k: v for k, v in updates.items() if k in allowed_fields}
    if update_data:
        await db.listings.update_one({"id": listing_id}, {"$set": update_data})
    updated_listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if isinstance(updated_listing.get("created_at"), str):
        updated_listing["created_at"] = datetime.fromisoformat(updated_listing["created_at"])
    if isinstance(updated_listing.get("auction_end_date"), str):
        updated_listing["auction_end_date"] = datetime.fromisoformat(updated_listing["auction_end_date"])
    return Listing(**updated_listing)

@api_router.delete("/listings/{listing_id}")
async def delete_listing(listing_id: str, current_user: User = Depends(get_current_user)):
    listing = await db.listings.find_one({"id": listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["seller_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    await db.listings.delete_one({"id": listing_id})
    return {"message": "Listing deleted successfully"}

@api_router.get("/marketplace/items")
async def get_marketplace_items(
    search: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    condition: Optional[str] = None,
    sort: str = "-promoted",  # Default: promoted first
    limit: int = 50,
    skip: int = 0,
    track_impression: bool = False
):
    """
    Decomposed marketplace view: Returns individual items from multi-item lots.
    Features:
    - Item-centric discovery (not lot-centric)
    - Promoted items appear first
    - Each item has individual Buy Now price, bid, and staggered end time
    - Tracks impressions for promoted items
    """
    # Query active multi-item auctions
    query = {"status": "active"}
    
    if category:
        query["category"] = category
    
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]
    
    # Fetch all active auctions
    auctions = await db.multi_item_listings.find(query, {"_id": 0}).to_list(None)
    
    # Decompose lots into individual items
    items = []
    
    for auction in auctions:
        # Track impressions for promoted auctions
        if auction.get("is_promoted") and track_impression:
            await db.multi_item_listings.update_one(
                {"id": auction["id"]},
                {"$inc": {"total_impressions": 1}}
            )
        
        for lot in auction.get("lots", []):
            # Skip sold out lots
            if lot.get("lot_status") == "sold_out":
                continue
            
            # Apply price filters
            current_price = lot.get("current_price", lot.get("starting_price", 0))
            if min_price is not None and current_price < min_price:
                continue
            if max_price is not None and current_price > max_price:
                continue
            
            # Apply condition filter
            if condition and lot.get("condition") != condition:
                continue
            
            # Calculate staggered end time
            # Item end time = base auction end + (lot_number * 1 minute)
            base_end_time = auction.get("auction_end_date")
            if isinstance(base_end_time, str):
                base_end_time = datetime.fromisoformat(base_end_time)
            
            lot_end_time = lot.get("lot_end_time")
            if not lot_end_time and base_end_time:
                # Calculate staggered time: base + (lot_number * 60 seconds)
                stagger_seconds = lot["lot_number"] * 60
                lot_end_time = base_end_time + timedelta(seconds=stagger_seconds)
            elif isinstance(lot_end_time, str):
                lot_end_time = datetime.fromisoformat(lot_end_time)
            
            # Build decomposed item
            item = {
                "id": f"{auction['id']}_lot{lot['lot_number']}",  # Composite ID
                "auction_id": auction["id"],
                "lot_number": lot["lot_number"],
                "title": lot["title"],
                "description": lot["description"],
                "category": auction.get("category"),
                "condition": lot.get("condition"),
                "images": lot.get("images", []),
                
                # Pricing
                "starting_price": lot.get("starting_price"),
                "current_price": current_price,
                "buy_now_price": lot.get("buy_now_price"),
                "buy_now_enabled": lot.get("buy_now_enabled", False),
                
                # Quantity
                "quantity": lot.get("quantity", 1),
                "available_quantity": lot.get("available_quantity", lot.get("quantity", 1)),
                "sold_quantity": lot.get("sold_quantity", 0),
                
                # Bidding
                "bid_count": lot.get("bid_count", 0),
                "highest_bidder_id": lot.get("highest_bidder_id"),
                
                # Timing
                "auction_end_date": lot_end_time.isoformat() if lot_end_time else None,
                "extension_count": lot.get("extension_count", 0),
                
                # Status
                "lot_status": lot.get("lot_status", "active"),
                "pricing_mode": lot.get("pricing_mode", "multiplied"),
                
                # Promotion (inherited from parent auction)
                "is_promoted": auction.get("is_promoted", False),
                "promotion_tier": auction.get("promotion_tier"),
                "is_featured": auction.get("is_featured", False),
                
                # Parent context
                "parent_auction_title": auction.get("title"),
                "total_lots_in_auction": len(auction.get("lots", [])),
                "seller_id": auction.get("seller_id"),
                
                # Location
                "city": auction.get("city"),
                "region": auction.get("region"),
                "country": auction.get("country"),
                
                # Metadata
                "created_at": auction.get("created_at")
            }
            
            items.append(item)
    
    # Sorting logic
    if sort == "-promoted":
        # Promoted items first (by tier), then by created_at
        promotion_weight = {"premium": 3, "standard": 2, "basic": 1, None: 0}
        items.sort(
            key=lambda x: (
                -promotion_weight.get(x.get("promotion_tier"), 0),  # Promoted first
                -1 if x.get("is_featured") else 0,  # Featured second
                -(x.get("created_at").timestamp() if isinstance(x.get("created_at"), datetime) else 0)  # Newest
            )
        )
    elif sort == "price":
        items.sort(key=lambda x: x.get("current_price", 0))
    elif sort == "-price":
        items.sort(key=lambda x: -x.get("current_price", 0))
    elif sort == "ending_soon":
        items.sort(
            key=lambda x: datetime.fromisoformat(x["auction_end_date"]) if x.get("auction_end_date") else datetime.max
        )
    else:  # Default: newest first
        items.sort(
            key=lambda x: -(x.get("created_at").timestamp() if isinstance(x.get("created_at"), datetime) else 0)
        )
    
    # Pagination
    total_items = len(items)
    paginated_items = items[skip:skip + limit]
    
    return {
        "items": paginated_items,
        "total": total_items,
        "limit": limit,
        "skip": skip,
        "has_more": (skip + limit) < total_items
    }

@api_router.post("/marketplace/items/{item_id}/track-click")
async def track_item_click(item_id: str):
    """Track clicks on marketplace items for promoted listings analytics"""
    # Parse composite ID: auction_id_lotN
    if "_lot" not in item_id:
        return {"success": False, "message": "Invalid item ID"}
    
    auction_id = item_id.split("_lot")[0]
    
    # Increment click count for auction
    await db.multi_item_listings.update_one(
        {"id": auction_id, "is_promoted": True},
        {"$inc": {"total_clicks": 1}}
    )
    
    return {"success": True}

@api_router.post("/bids")
async def place_bid(bid_data: BidCreate, current_user: User = Depends(get_current_user)):
    # ========== LOAD MARKETPLACE SETTINGS ==========
    settings = await get_marketplace_settings()
    
    listing = await db.listings.find_one({"id": bid_data.listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["seller_id"] == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot bid on your own listing")
    if listing["status"] != "active":
        raise HTTPException(status_code=400, detail="Listing is not active")
    if isinstance(listing.get("auction_end_date"), str):
        auction_end = datetime.fromisoformat(listing["auction_end_date"])
    else:
        auction_end = listing["auction_end_date"]
    
    now = datetime.now(timezone.utc)
    
    # ========== ANTI-SNIPING LOGIC (Configurable) ==========
    # Get anti-sniping settings from admin configuration
    anti_sniping_enabled = settings.get("enable_anti_sniping", True)
    anti_sniping_window_minutes = settings.get("anti_sniping_window_minutes", 2)
    ANTI_SNIPE_WINDOW = anti_sniping_window_minutes * 60  # Convert to seconds
    GRACE_PERIOD = 5  # 5 second grace for network latency
    
    time_remaining = (auction_end - now).total_seconds()
    extension_applied = False
    new_auction_end = None
    
    # Check if auction has truly ended (beyond grace period)
    if time_remaining < -GRACE_PERIOD:
        raise HTTPException(status_code=400, detail="Auction has ended")
    
    # If anti-sniping is enabled and bid is within final window, extend
    if anti_sniping_enabled and time_remaining <= ANTI_SNIPE_WINDOW:
        # Calculate new end time: Time of Bid + 120 seconds
        new_auction_end = now + timedelta(seconds=ANTI_SNIPE_WINDOW)
        extension_applied = True
        logger.info(f"⏰ Anti-sniping triggered: listing={bid_data.listing_id}, time_remaining={time_remaining:.1f}s, new_end={new_auction_end.isoformat()}")
    
    # Calculate minimum bid using configurable increment from settings
    min_increment = settings.get("minimum_bid_increment", 1.0)
    min_bid = listing["current_price"] + min_increment
    
    if bid_data.amount <= listing["current_price"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Your bid must be at least ${min_bid:.2f} to lead."
        )
    
    # Also validate the bid meets minimum increment
    if bid_data.amount < min_bid:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum bid increment is ${min_increment:.2f}. Your bid must be at least ${min_bid:.2f}."
        )
    
    # Create bid
    bid = Bid(listing_id=bid_data.listing_id, bidder_id=current_user.id, amount=bid_data.amount)
    bid_dict = bid.model_dump()
    bid_dict["created_at"] = bid_dict["created_at"].isoformat()
    
    # Insert bid and update listing atomically
    await db.bids.insert_one(bid_dict)
    new_bid_count = listing.get("bid_count", 0) + 1
    
    update_fields = {
        "current_price": bid_data.amount,
        "highest_bidder_id": current_user.id
    }
    
    # Apply time extension if anti-sniping triggered
    if extension_applied and new_auction_end:
        update_fields["auction_end_date"] = new_auction_end.isoformat()
        update_fields["extension_count"] = listing.get("extension_count", 0) + 1
    
    await db.listings.update_one(
        {"id": bid_data.listing_id}, 
        {
            "$set": update_fields,
            "$inc": {"bid_count": 1}
        }
    )
    
    # Real-time broadcast with personalized status AND time extension
    broadcast_data = {
        'bid_count': new_bid_count,
        'current_price': bid_data.amount
    }
    
    # Include time extension info in broadcast (with epoch timestamp for timezone safety)
    if extension_applied and new_auction_end:
        broadcast_data['time_extended'] = True
        broadcast_data['new_auction_end'] = new_auction_end.isoformat()
        broadcast_data['new_auction_end_epoch'] = get_epoch_timestamp(new_auction_end)  # Timezone-safe
        broadcast_data['server_time_epoch'] = get_server_timestamp()
        broadcast_data['extension_reason'] = 'anti_sniping'
    
    await manager.broadcast_bid_update(
        bid_data.listing_id,
        {
            'id': bid_dict['id'],
            'bidder_id': current_user.id,
            'amount': bid_data.amount,
            'created_at': bid_dict['created_at']
        },
        broadcast_data
    )
    
    logger.info(f"Bid placed: listing={bid_data.listing_id}, bidder={current_user.id}, amount={bid_data.amount}, extension={extension_applied}")
    
    # Return bid with extension info
    response = bid.model_dump()
    response["created_at"] = bid_dict["created_at"]
    if extension_applied:
        response["extension_applied"] = True
        response["new_auction_end"] = new_auction_end.isoformat()
    
    return response

@api_router.post("/buy-now")
async def purchase_buy_now(
    purchase: BuyNowPurchase,
    current_user: User = Depends(get_current_user)
):
    """
    Process Buy Now purchase for multi-item lots.
    Implements atomic quantity decrement and partial lot liquidation.
    """
    # ========== CHECK IF BUY NOW IS GLOBALLY ENABLED ==========
    settings = await get_marketplace_settings()
    if not settings.get("enable_buy_now", True):
        raise HTTPException(
            status_code=403, 
            detail="Buy Now feature is currently disabled by admin. Please place a bid instead."
        )
    
    # Fetch the auction
    auction = await db.multi_item_listings.find_one(
        {"id": purchase.auction_id},
        {"_id": 0}
    )
    
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    if auction["status"] != "active":
        raise HTTPException(status_code=400, detail="Auction is not active")
    
    # Find the specific lot
    lot_index = None
    target_lot = None
    
    for idx, lot in enumerate(auction["lots"]):
        if lot["lot_number"] == purchase.lot_number:
            lot_index = idx
            target_lot = lot
            break
    
    if not target_lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    
    # Validate Buy Now is enabled for this specific lot
    if not target_lot.get("buy_now_enabled", False):
        raise HTTPException(status_code=400, detail="Buy Now not available for this lot")
    
    if not target_lot.get("buy_now_price"):
        raise HTTPException(status_code=400, detail="Buy Now price not set")
    
    # Check available quantity
    available_qty = target_lot.get("available_quantity", target_lot["quantity"])
    
    if available_qty <= 0:
        raise HTTPException(status_code=400, detail="Item sold out")
    
    if purchase.quantity > available_qty:
        raise HTTPException(
            status_code=400,
            detail=f"Only {available_qty} units available"
        )
    
    # Calculate total
    price_per_unit = target_lot["buy_now_price"]
    total_amount = price_per_unit * purchase.quantity
    
    # Atomic update: decrement quantity
    new_available_qty = available_qty - purchase.quantity
    new_sold_qty = target_lot.get("sold_quantity", 0) + purchase.quantity
    
    # Determine new lot status
    if new_available_qty == 0:
        new_lot_status = "sold_out"
    elif new_sold_qty > 0:
        new_lot_status = "partially_sold"
    else:
        new_lot_status = target_lot.get("lot_status", "active")
    
    # Update lot in database (atomic operation)
    update_fields = {
        f"lots.{lot_index}.available_quantity": new_available_qty,
        f"lots.{lot_index}.sold_quantity": new_sold_qty,
        f"lots.{lot_index}.lot_status": new_lot_status
    }
    
    # If sold out, close the auction for this lot
    if new_available_qty == 0:
        update_fields[f"lots.{lot_index}.lot_status"] = "sold_out"
    
    result = await db.multi_item_listings.update_one(
        {"id": purchase.auction_id},
        {"$set": update_fields}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Failed to update inventory")
    
    # Create transaction record
    transaction = BuyNowTransaction(
        auction_id=purchase.auction_id,
        lot_number=purchase.lot_number,
        buyer_id=current_user.id,
        quantity_purchased=purchase.quantity,
        price_per_unit=price_per_unit,
        total_amount=total_amount,
        payment_status="pending"
    )
    
    transaction_dict = transaction.model_dump()
    transaction_dict["transaction_date"] = transaction_dict["transaction_date"].isoformat()
    
    await db.buy_now_transactions.insert_one(transaction_dict)
    
    # Real-time broadcast to all viewers
    await manager.broadcast(
        purchase.auction_id,
        {
            "type": "BUY_NOW_PURCHASE",
            "auction_id": purchase.auction_id,
            "lot_number": purchase.lot_number,
            "quantity_purchased": purchase.quantity,
            "available_quantity": new_available_qty,
            "lot_status": new_lot_status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )
    
    logger.info(
        f"Buy Now purchase: auction={purchase.auction_id}, "
        f"lot={purchase.lot_number}, buyer={current_user.id}, "
        f"qty={purchase.quantity}, total=${total_amount}"
    )
    
    return {
        "success": True,
        "transaction_id": transaction.id,
        "total_amount": total_amount,
        "available_quantity": new_available_qty,
        "lot_status": new_lot_status,
        "message": "Purchase successful! Payment pending."
    }

@api_router.get("/bids/listing/{listing_id}")
async def get_listing_bids(listing_id: str, limit: int = 20):
    """Get bids for a listing with bidder information"""
    bids = await db.bids.find({"listing_id": listing_id}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Enrich bids with bidder information
    enriched_bids = []
    for bid in bids:
        # Get bidder user info
        bidder = await db.users.find_one({"id": bid["bidder_id"]}, {"_id": 0, "name": 1, "picture": 1})
        
        # Format datetime
        if isinstance(bid.get("created_at"), str):
            bid["created_at"] = datetime.fromisoformat(bid["created_at"])
        
        enriched_bids.append({
            **bid,
            "bidder_name": bidder.get("name") if bidder else "Anonymous",
            "bidder_avatar": bidder.get("picture") if bidder else None,
            "created_at": bid["created_at"].isoformat() if isinstance(bid["created_at"], datetime) else bid["created_at"]
        })
    
    return enriched_bids

@api_router.get("/categories", response_model=List[Category])
async def get_categories():
    categories = await db.categories.find({}, {"_id": 0}).to_list(100)
    return [Category(**cat) for cat in categories]

@api_router.post("/categories", response_model=Category)
async def create_category(category: Category, current_user: User = Depends(get_current_user)):
    cat_dict = category.model_dump()
    await db.categories.insert_one(cat_dict)
    return category

@api_router.get("/dashboard/seller")
async def get_seller_dashboard(current_user: User = Depends(get_current_user)):
    listings = await db.listings.find({"seller_id": current_user.id}, {"_id": 0}).to_list(1000)
    active_listings = [l for l in listings if l["status"] == "active"]
    sold_listings = [l for l in listings if l["status"] == "sold"]
    draft_listings = [l for l in listings if l["status"] == "draft"]
    total_sales = sum(l["current_price"] for l in sold_listings)
    return {
        "active_listings": len(active_listings), "sold_listings": len(sold_listings),
        "draft_listings": len(draft_listings), "total_sales": total_sales, "listings": listings
    }

@api_router.get("/dashboard/buyer")
async def get_buyer_dashboard(current_user: User = Depends(get_current_user)):
    bids = await db.bids.find({"bidder_id": current_user.id}, {"_id": 0}).to_list(1000)
    listing_ids = list(set(bid["listing_id"] for bid in bids))
    listings = await db.listings.find({"id": {"$in": listing_ids}}, {"_id": 0}).to_list(1000)
    
    # Fetch watchlist items
    watchlist_items = await db.watchlist.find({"user_id": current_user.id}, {"_id": 0}).to_list(100)
    watchlist_listing_ids = [item["listing_id"] for item in watchlist_items]
    watchlist_listings = await db.listings.find(
        {"id": {"$in": watchlist_listing_ids}, "status": {"$ne": "deleted"}},
        {"_id": 0}
    ).to_list(100)
    
    return {
        "total_bids": len(bids),
        "active_bids": len([b for b in bids if any(l["status"] == "active" for l in listings if l["id"] == b["listing_id"])]),
        "won_items": len([l for l in listings if l["status"] == "sold"]),
        "bids": bids,
        "listings": listings,
        "watchlist": watchlist_listings
    }

@api_router.post("/payments/checkout")
async def create_checkout_session(request: Request, data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    listing_id = data.get("listing_id")
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    buyer_fee = 0.05 if current_user.account_type == "personal" else 0.045
    total_amount = listing["current_price"] * (1 + buyer_fee)
    host_url = str(request.base_url)
    success_url = f"{data.get('origin_url')}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{data.get('origin_url')}/listing/{listing_id}"
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
    checkout_request = CheckoutSessionRequest(
        amount=total_amount, currency="usd", success_url=success_url, cancel_url=cancel_url,
        metadata={"user_id": current_user.id, "listing_id": listing_id, "buyer_fee": str(buyer_fee)}
    )
    session: CheckoutSessionResponse = await stripe_checkout.create_checkout_session(checkout_request)
    transaction = PaymentTransaction(
        session_id=session.session_id, user_id=current_user.id, listing_id=listing_id,
        amount=total_amount, currency="usd", payment_status="pending", metadata=checkout_request.metadata
    )
    trans_dict = transaction.model_dump()
    trans_dict["created_at"] = trans_dict["created_at"].isoformat()
    await db.payment_transactions.insert_one(trans_dict)
    return {"url": session.url, "session_id": session.session_id}

@api_router.get("/payments/status/{session_id}")
async def get_payment_status(session_id: str, current_user: User = Depends(get_current_user)):
    webhook_url = "http://localhost:8001/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
    status: CheckoutStatusResponse = await stripe_checkout.get_checkout_status(session_id)
    transaction = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if transaction and status.payment_status == "paid" and transaction["payment_status"] != "paid":
        await db.payment_transactions.update_one({"session_id": session_id}, {"$set": {"payment_status": "paid"}})
        listing_id = transaction.get("listing_id")
        if listing_id:
            await db.listings.update_one({"id": listing_id}, {"$set": {"status": "sold"}})
    return status.model_dump()

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("Stripe-Signature")
    webhook_url = "http://localhost:8001/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
    try:
        webhook_response = await stripe_checkout.handle_webhook(body, signature)
        if webhook_response.payment_status == "paid":
            await db.payment_transactions.update_one({"session_id": webhook_response.session_id}, {"$set": {"payment_status": "paid"}})
            transaction = await db.payment_transactions.find_one({"session_id": webhook_response.session_id})
            if transaction and transaction.get("listing_id"):
                await db.listings.update_one({"id": transaction["listing_id"]}, {"$set": {"status": "sold"}})
            # Handle promotion payment
            if transaction and transaction.get("metadata") and transaction["metadata"].get("promotion_id"):
                promotion_id = transaction["metadata"]["promotion_id"]
                await db.promotions.update_one({"id": promotion_id}, {"$set": {"status": "active", "payment_status": "paid"}})
                promotion = await db.promotions.find_one({"id": promotion_id})
                if promotion and promotion.get("listing_id"):
                    await db.listings.update_one({"id": promotion["listing_id"]}, {"$set": {"is_promoted": True}})
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=400, detail="Webhook error")

@api_router.post("/payments/promote")
async def create_promotion_checkout(request: Request, data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    promotion_id = data.get("promotion_id")
    amount = data.get("amount")
    
    if not promotion_id or not amount:
        raise HTTPException(status_code=400, detail="Missing promotion_id or amount")
    
    promotion = await db.promotions.find_one({"id": promotion_id}, {"_id": 0})
    if not promotion:
        raise HTTPException(status_code=404, detail="Promotion not found")
    
    if promotion["seller_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    host_url = str(request.base_url)
    success_url = f"{data.get('origin_url')}/listing/{promotion['listing_id']}?promoted=true"
    cancel_url = f"{data.get('origin_url')}/listing/{promotion['listing_id']}"
    webhook_url = f"{host_url}api/webhook/stripe"
    
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
    checkout_request = CheckoutSessionRequest(
        amount=amount, 
        currency="usd", 
        success_url=success_url, 
        cancel_url=cancel_url,
        metadata={"user_id": current_user.id, "promotion_id": promotion_id, "listing_id": promotion["listing_id"]}
    )
    
    session: CheckoutSessionResponse = await stripe_checkout.create_checkout_session(checkout_request)
    
    transaction = PaymentTransaction(
        session_id=session.session_id, 
        user_id=current_user.id, 
        listing_id=promotion["listing_id"],
        amount=amount, 
        currency="usd", 
        payment_status="pending", 
        metadata={"promotion_id": promotion_id, **checkout_request.metadata}
    )
    trans_dict = transaction.model_dump()
    trans_dict["created_at"] = trans_dict["created_at"].isoformat()
    await db.payment_transactions.insert_one(trans_dict)
    
    return {"url": session.url, "session_id": session.session_id}

@app.websocket("/api/ws/listings/{listing_id}")
async def websocket_endpoint(
    websocket: WebSocket, 
    listing_id: str, 
    user_id: Optional[str] = Query(default=None)
):
    """
    Enhanced WebSocket endpoint for real-time bidding updates.
    Supports personalized status updates (LEADING/OUTBID).
    Includes ping/pong heartbeat for connection health.
    """
    logger.info(f"🔌 WebSocket connection request: listing_id={listing_id}, user_id={user_id}")
    
    await manager.connect(websocket, listing_id, user_id)
    logger.info(f"✅ WebSocket connected: listing_id={listing_id}, user_id={user_id}, total_viewers={len(manager.active_connections.get(listing_id, []))}")
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            'type': 'CONNECTION_ESTABLISHED',
            'listing_id': listing_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'message': 'Real-time updates active'
        })
        
        # Send current listing state
        listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
        if listing:
            # Get highest bidder
            highest_bid = await db.bids.find_one(
                {"listing_id": listing_id},
                {"_id": 0},
                sort=[("amount", -1)]
            )
            
            highest_bidder_id = highest_bid.get('bidder_id') if highest_bid else None
            bid_status = 'LEADING' if user_id and user_id == highest_bidder_id else 'OUTBID' if highest_bid else 'NO_BIDS'
            
            # Include auction_end_date for countdown synchronization
            auction_end_date = listing.get('auction_end_date')
            if auction_end_date and not isinstance(auction_end_date, str):
                auction_end_date = auction_end_date.isoformat()
            
            # CRITICAL: Send epoch timestamp for timezone-safe countdown calculation
            auction_end_epoch = get_epoch_timestamp(listing.get('auction_end_date'))
            server_time_epoch = get_server_timestamp()
            
            # Check if auction has actually ended
            now = datetime.now(timezone.utc)
            if auction_end_date:
                try:
                    end_dt = datetime.fromisoformat(auction_end_date.replace('Z', '+00:00'))
                    auction_active = now < end_dt
                except:
                    auction_active = True
            else:
                auction_active = True
            
            await websocket.send_json({
                'type': 'INITIAL_STATE',
                'listing_id': listing_id,
                'current_price': listing.get('current_price'),
                'bid_count': listing.get('bid_count', 0),
                'highest_bidder_id': highest_bidder_id,
                'bid_status': bid_status,
                'auction_end_date': auction_end_date,  # ISO string (backup)
                'auction_end_epoch': auction_end_epoch,  # Unix timestamp (primary - timezone-safe)
                'server_time_epoch': server_time_epoch,  # Server's current time for sync
                'auction_active': auction_active,
                'timestamp': now.isoformat()
            })
        
        # Keep connection alive with heartbeat
        while True:
            try:
                # Receive and handle messages
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                data = json.loads(message) if message else {}
                
                # Handle ping/pong for connection health
                if data.get('type') == 'PING':
                    await websocket.send_json({
                        'type': 'PONG',
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                try:
                    await websocket.send_json({
                        'type': 'HEARTBEAT',
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                except:
                    break
                    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: listing_id={listing_id}, user_id={user_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        manager.disconnect(websocket, listing_id, user_id)

@api_router.post("/payment-methods")
async def add_payment_method(data: PaymentMethodCreate, current_user: User = Depends(get_current_user)):
    try:
        payment_method = stripe.PaymentMethod.retrieve(data.payment_method_id)
        stripe.PaymentMethod.attach(data.payment_method_id, customer=current_user.id)
        
        intent = stripe.PaymentIntent.create(
            amount=100,
            currency='usd',
            payment_method=data.payment_method_id,
            customer=current_user.id,
            confirm=True,
            return_url='https://bid-masters-1.preview.emergentagent.com'
        )
        
        is_verified = intent.status == 'succeeded' or intent.status == 'requires_capture'
        
        pm_doc = {
            "id": str(uuid.uuid4()),
            "user_id": current_user.id,
            "stripe_payment_method_id": data.payment_method_id,
            "card_brand": payment_method.card.brand,
            "last4": payment_method.card.last4,
            "exp_month": payment_method.card.exp_month,
            "exp_year": payment_method.card.exp_year,
            "is_verified": is_verified,
            "is_default": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.payment_methods.insert_one(pm_doc)
        
        if is_verified:
            stripe.PaymentIntent.cancel(intent.id)
        
        return PaymentMethodResponse(**pm_doc)
    except Exception as e:
        logger.error(f"Payment method error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.get("/payment-methods")
async def get_payment_methods(current_user: User = Depends(get_current_user)):
    methods = await db.payment_methods.find({"user_id": current_user.id}, {"_id": 0}).to_list(100)
    return methods

@api_router.delete("/payment-methods/{method_id}")
async def delete_payment_method(method_id: str, current_user: User = Depends(get_current_user)):
    method = await db.payment_methods.find_one({"id": method_id, "user_id": current_user.id})
    if not method:
        raise HTTPException(status_code=404, detail="Payment method not found")
    
    try:
        stripe.PaymentMethod.detach(method["stripe_payment_method_id"])
    except:
        pass
    
    await db.payment_methods.delete_one({"id": method_id})
    return {"message": "Payment method deleted"}

@api_router.put("/profile")
async def update_profile(updates: ProfileUpdate, current_user: User = Depends(get_current_user)):
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    if update_data:
        await db.users.update_one({"id": current_user.id}, {"$set": update_data})
    updated_user = await db.users.find_one({"id": current_user.id}, {"_id": 0, "password": 0})
    return updated_user

@api_router.post("/listings/search/location")
async def search_by_location(params: LocationSearchParams):
    query = {"status": "active"}
    
    if params.category:
        query["category"] = params.category
    if params.min_price is not None:
        query["current_price"] = {"$gte": params.min_price}
    if params.max_price is not None:
        if "current_price" in query:
            query["current_price"]["$lte"] = params.max_price
        else:
            query["current_price"] = {"$lte": params.max_price}
    
    if params.latitude and params.longitude:
        radius_in_radians = params.radius_km / 6371.0
        query["$or"] = [
            {
                "latitude": {
                    "$gte": params.latitude - radius_in_radians * 57.2958,
                    "$lte": params.latitude + radius_in_radians * 57.2958
                },
                "longitude": {
                    "$gte": params.longitude - radius_in_radians * 57.2958,
                    "$lte": params.longitude + radius_in_radians * 57.2958
                }
            },
            {"latitude": None}
        ]
    
    listings = await db.listings.find(query, {"_id": 0}).limit(50).to_list(50)
    
    for listing in listings:
        if isinstance(listing.get("created_at"), str):
            listing["created_at"] = datetime.fromisoformat(listing["created_at"])
        if isinstance(listing.get("auction_end_date"), str):
            listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])
    
    return [Listing(**listing) for listing in listings]

@api_router.get("/config/google-maps-key")
async def get_google_maps_key():
    return {"api_key": google_maps_key}

@api_router.get("/affiliate/stats")
async def get_affiliate_stats(current_user: User = Depends(get_current_user)):
    referrals = await db.referrals.find({"affiliate_id": current_user.id}, {"_id": 0}).to_list(1000)
    
    total_referrals = len(referrals)
    active_referrals = len([r for r in referrals if r.get("status") == "active"])
    
    earnings = await db.affiliate_earnings.find({"affiliate_id": current_user.id}, {"_id": 0}).to_list(1000)
    total_earnings = sum(e.get("commission_amount", 0) for e in earnings)
    pending_earnings = sum(e.get("commission_amount", 0) for e in earnings if e.get("status") == "pending")
    paid_earnings = sum(e.get("commission_amount", 0) for e in earnings if e.get("status") == "paid")
    
    return {
        "affiliate_code": current_user.affiliate_code,
        "referral_link": f"https://bid-masters-1.preview.emergentagent.com/auth?ref={current_user.affiliate_code}",
        "total_referrals": total_referrals,
        "active_referrals": active_referrals,
        "total_earnings": total_earnings,
        "pending_earnings": pending_earnings,
        "paid_earnings": paid_earnings,
        "earnings_history": earnings,
        "referrals": referrals
    }

@api_router.post("/affiliate/withdraw")
async def request_withdrawal(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    amount = data.get("amount")
    method = data.get("method", "bank_transfer")
    
    earnings = await db.affiliate_earnings.find({
        "affiliate_id": current_user.id,
        "status": "pending"
    }).to_list(1000)
    
    available = sum(e.get("commission_amount", 0) for e in earnings)
    
    if amount > available:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    withdrawal_request = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "amount": amount,
        "method": method,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.withdrawal_requests.insert_one(withdrawal_request)
    
    return {"message": "Withdrawal request submitted", "request_id": withdrawal_request["id"]}

@api_router.post("/messages")
async def send_message(msg: MessageCreate, current_user: User = Depends(get_current_user)):
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
    
    # Store listing_id in conversation for reference cards
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
    
    # Send via real-time messaging WebSocket if recipient is in conversation
    sender_info = {"id": current_user.id, "name": current_user.name, "picture": current_user.picture}
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
    
    # Also send via global notification channel for users not in conversation
    if not message_manager.is_user_in_conversation(conversation_id, msg.receiver_id):
        await manager.send_to_user(msg.receiver_id, {
            "type": "new_message_notification",
            "conversation_id": conversation_id,
            "sender_name": current_user.name,
            "sender_picture": current_user.picture,
            "preview": msg.content[:50] + ("..." if len(msg.content) > 50 else ""),
            "message": msg_dict,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    return message

@api_router.get("/conversations")
async def get_conversations(current_user: User = Depends(get_current_user)):
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

@api_router.get("/messages/unread-count")
async def get_unread_message_count(current_user: User = Depends(get_current_user)):
    """Get total count of unread messages for current user"""
    count = await db.messages.count_documents({
        "receiver_id": current_user.id,
        "is_read": False
    })
    return {"unread_count": count}

@api_router.get("/messages/{conversation_id}")
async def get_messages(conversation_id: str, current_user: User = Depends(get_current_user), limit: int = 50):
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

@api_router.get("/messages")
async def get_all_user_messages(
    current_user: User = Depends(get_current_user),
    listing_id: Optional[str] = None,
    limit: int = 50
):
    """Get all messages for current user, optionally filtered by listing_id"""
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
    
    # Mark messages as read if user is the receiver
    await db.messages.update_many(
        {"receiver_id": current_user.id, "is_read": False},
        {"$set": {"is_read": True}}
    )
    
    for msg in messages:
        if isinstance(msg.get("created_at"), str):
            msg["created_at"] = datetime.fromisoformat(msg["created_at"])
    
    return [Message(**msg) for msg in messages]

# ========== MESSAGING ATTACHMENTS & ITEM SHARING ==========

@api_router.post("/messages/attachment")
async def upload_message_attachment(
    file: UploadFile = File(...),
    receiver_id: str = Form(...),
    conversation_id: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a file attachment in a message conversation (Max 10MB)
    Supported formats: JPG, PNG, GIF, WebP, PDF
    """
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
    unique_filename = f"msg_{conversation_id}_{uuid.uuid4().hex[:8]}.{file_ext}"
    
    # Store file (in production, use S3/Cloudinary)
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
    
    # Try to notify via WebSocket
    try:
        await messaging_manager.send_message(conversation_id, {
            "type": "NEW_MESSAGE",
            "message": message
        })
    except Exception as e:
        logger.warning(f"Could not send WebSocket notification: {e}")
    
    return {"status": "success", "message": message}


@api_router.post("/messages/share-item-details")
async def share_item_details_in_chat(
    data: Dict[str, str],
    current_user: User = Depends(get_current_user)
):
    """
    Share item/listing details as a rich card in the chat
    Used by sellers to share lot summaries with buyers
    """
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
        # Try multi-item listings
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
        await messaging_manager.send_message(conversation_id, {
            "type": "NEW_MESSAGE",
            "message": message
        })
    except Exception as e:
        logger.warning(f"Could not send WebSocket notification: {e}")
    
    return {"status": "success", "message": message}


async def create_auction_won_conversation(
    listing_id: str,
    seller_id: str,
    winner_id: str,
    final_price: float,
    item_title: str
):
    """
    Automatically create a conversation between seller and winning bidder
    when an auction ends. Called from the auction end handler.
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


@api_router.get("/uploads/messages/{filename}")
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


@api_router.post("/upload-document")
async def upload_document(
    file_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """
    Upload a document (PDF or image) as base64 with 10MB validation
    Expected format: {
        "filename": "document.pdf",
        "content_type": "application/pdf",
        "base64_content": "base64_encoded_string"
    }
    """
    import base64
    
    filename = file_data.get("filename", "")
    content_type = file_data.get("content_type", "")
    base64_content = file_data.get("base64_content", "")
    
    # Validate file type (PDF or images)
    allowed_types = ["application/pdf", "image/png", "image/jpeg", "image/jpg"]
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: PDF, PNG, JPG. Got: {content_type}"
        )
    
    # Validate base64 content exists
    if not base64_content:
        raise HTTPException(status_code=400, detail="No file content provided")
    
    # Calculate file size (base64 decoded size)
    try:
        # Remove data URL prefix if present (e.g., "data:application/pdf;base64,")
        if "base64," in base64_content:
            base64_content = base64_content.split("base64,")[1]
        
        decoded_content = base64.b64decode(base64_content)
        file_size_mb = len(decoded_content) / (1024 * 1024)
        
        # 10MB limit
        if file_size_mb > 10:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is 10MB. File size: {file_size_mb:.2f}MB"
            )
        
        return {
            "success": True,
            "filename": filename,
            "content_type": content_type,
            "size_mb": round(file_size_mb, 2),
            "base64_content": base64_content
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 content: {str(e)}")

@api_router.post("/multi-item-listings")
async def create_multi_item_listing(listing_data: MultiItemListingCreate, current_user: User = Depends(get_current_user)):
    # ========== ENFORCE MARKETPLACE SETTINGS ==========
    settings = await get_marketplace_settings()
    
    # Check 1: Multi-lot access restriction
    if not settings.get("allow_all_users_multi_lot", True):
        # Only business accounts can create multi-lot auctions
        if current_user.account_type != "business":
            raise HTTPException(
                status_code=403, 
                detail="Multi-lot auctions are restricted to business accounts. Please upgrade your account or contact support."
            )
    
    # Check 2: Quota - Maximum active auctions per user
    max_active = settings.get("max_active_auctions_per_user", 20)
    active_count = await db.multi_item_listings.count_documents({
        "seller_id": current_user.id,
        "status": {"$in": ["active", "upcoming"]}
    })
    if active_count >= max_active:
        raise HTTPException(
            status_code=400,
            detail=f"You have reached the maximum limit of {max_active} active auctions. Please wait for current auctions to end."
        )
    
    # Check 3: Quota - Maximum lots per auction
    max_lots = settings.get("max_lots_per_auction", 50)
    if len(listing_data.lots) > max_lots:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {max_lots} lots allowed per auction. You submitted {len(listing_data.lots)} lots."
        )
    
    # Determine status based on auction_start_date and seller approval requirement
    now = datetime.now(timezone.utc)
    status = "active"  # Default to active
    
    # Check 4: Require approval for new sellers
    if settings.get("require_approval_new_sellers", False):
        # Check if user has completed any auctions
        completed_count = await db.multi_item_listings.count_documents({
            "seller_id": current_user.id,
            "status": "completed"
        })
        if completed_count < 1:
            status = "pending"  # Requires admin approval
            logger.info(f"📋 New seller {current_user.email} listing set to PENDING for approval")
    
    if listing_data.auction_start_date:
        # If start date is in the future, set to upcoming (unless pending)
        if listing_data.auction_start_date > now and status != "pending":
            status = "upcoming"
    
    # Auto-detect currency if not provided
    currency = listing_data.currency
    if not currency:
        currency = detect_currency_from_location(
            city=listing_data.city,
            region=listing_data.region
        )
    
    # Get tax rates based on currency
    tax_rates = get_tax_rates_for_currency(currency)
    
    # Auto-Promotion: Premium (3 days) and VIP (7 days) users get featured listings
    is_featured = False
    promotion_expiry = None
    
    if current_user.subscription_tier == "premium":
        is_featured = True
        promotion_expiry = now + timedelta(days=3)
    elif current_user.subscription_tier == "vip":
        is_featured = True
        promotion_expiry = now + timedelta(days=7)
    
    # Calculate staggered lot_end_time (1 minute per lot)
    # Start from auction_start_date if provided, otherwise use current time
    auction_start = listing_data.auction_start_date or now
    lots_with_end_time = []
    
    for idx, lot in enumerate(listing_data.lots):
        lot_dict = lot.model_dump()
        # Each lot ends 1 minute after the previous one (index 0 = start + 1 min, index 1 = start + 2 min, etc.)
        lot_dict['lot_end_time'] = auction_start + timedelta(minutes=idx + 1)
        lots_with_end_time.append(lot_dict)
    
    listing = MultiItemListing(
        seller_id=current_user.id,
        title=listing_data.title,
        description=listing_data.description,
        category=listing_data.category,
        location=listing_data.location,
        city=listing_data.city,
        region=listing_data.region,
        auction_end_date=listing_data.auction_end_date,
        auction_start_date=listing_data.auction_start_date,
        lots=lots_with_end_time,
        total_lots=len(listing_data.lots),
        status=status,
        currency=currency,
        tax_rate_gst=tax_rates["tax_rate_gst"],
        tax_rate_qst=tax_rates["tax_rate_qst"],
        is_featured=is_featured,
        promotion_expiry=promotion_expiry,
        documents=listing_data.documents,
        shipping_info=listing_data.shipping_info,
        visit_availability=listing_data.visit_availability,
        auction_terms_en=listing_data.auction_terms_en,
        auction_terms_fr=listing_data.auction_terms_fr
    )
    
    listing_dict = listing.model_dump()
    listing_dict["auction_end_date"] = listing_dict["auction_end_date"].isoformat()
    listing_dict["created_at"] = listing_dict["created_at"].isoformat()
    if listing_dict["auction_start_date"]:
        listing_dict["auction_start_date"] = listing_dict["auction_start_date"].isoformat()
    if listing_dict["promotion_expiry"]:
        listing_dict["promotion_expiry"] = listing_dict["promotion_expiry"].isoformat()
    
    # Serialize lot_end_time for each lot
    for lot in listing_dict.get("lots", []):
        if lot.get("lot_end_time"):
            lot["lot_end_time"] = lot["lot_end_time"].isoformat()
    
    await db.multi_item_listings.insert_one(listing_dict)
    
    return listing

@api_router.get("/multi-item-listings")
async def get_multi_item_listings(
    limit: int = 50, 
    skip: int = 0, 
    status: Optional[str] = None,
    category: Optional[str] = None,
    region: Optional[str] = None,
    currency: Optional[str] = None,
    search: Optional[str] = None
):
    # Build query filter
    query = {}
    
    # Status filter - default to both active and upcoming
    if status:
        query["status"] = status
    else:
        # Show both active and upcoming listings by default
        query["status"] = {"$in": ["active", "upcoming"]}
    
    # Category filter
    if category:
        query["category"] = category
    
    # Region filter
    if region:
        query["region"] = region
    
    # Currency filter
    if currency:
        query["currency"] = currency
    
    # Search filter (title or description)
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]
    
    listings = await db.multi_item_listings.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    for listing in listings:
        if isinstance(listing.get("created_at"), str):
            listing["created_at"] = datetime.fromisoformat(listing["created_at"])
        if isinstance(listing.get("auction_end_date"), str):
            listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])
        if isinstance(listing.get("auction_start_date"), str):
            listing["auction_start_date"] = datetime.fromisoformat(listing["auction_start_date"])
        
        # Deserialize lot_end_time for each lot
        for lot in listing.get("lots", []):
            if isinstance(lot.get("lot_end_time"), str):
                lot["lot_end_time"] = datetime.fromisoformat(lot["lot_end_time"])
    
    return [MultiItemListing(**listing) for listing in listings]

@api_router.get("/multi-item-listings/{listing_id}")
async def get_multi_item_listing(listing_id: str):
    listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    if isinstance(listing.get("created_at"), str):
        listing["created_at"] = datetime.fromisoformat(listing["created_at"])
    if isinstance(listing.get("auction_end_date"), str):
        listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])
    if isinstance(listing.get("auction_start_date"), str):
        listing["auction_start_date"] = datetime.fromisoformat(listing["auction_start_date"])
    
    # Deserialize lot_end_time for each lot
    for lot in listing.get("lots", []):
        if isinstance(lot.get("lot_end_time"), str):
            lot["lot_end_time"] = datetime.fromisoformat(lot["lot_end_time"])
    
    return MultiItemListing(**listing)

@api_router.get("/multi-item-listings/{listing_id}/terms/pdf")
async def export_auction_terms_pdf(listing_id: str):
    """
    Export auction terms as a PDF file.
    Includes bilingual terms if both EN and FR are provided.
    """
    from fastapi.responses import FileResponse
    from weasyprint import HTML, CSS
    import os
    
    try:
        # Get listing
        listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
        if not listing:
            raise HTTPException(status_code=404, detail="Auction not found")
        
        # Get seller info
        seller = await db.users.find_one({"id": listing["seller_id"]}, {"_id": 0, "password": 0})
        seller_name = seller.get("company_name") or seller.get("name", "Unknown Seller")
        
        # Check if terms exist
        terms_en = listing.get("auction_terms_en", "")
        terms_fr = listing.get("auction_terms_fr", "")
        
        if not terms_en and not terms_fr:
            raise HTTPException(status_code=404, detail="No auction terms available")
        
        # Build HTML content
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @page {{
                    size: A4;
                    margin: 2cm;
                }}
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 2px solid #2563eb;
                }}
                .header h1 {{
                    color: #2563eb;
                    margin: 0 0 10px 0;
                }}
                .header p {{
                    margin: 5px 0;
                    color: #666;
                }}
                .section {{
                    margin: 30px 0;
                }}
                .section-title {{
                    font-size: 20px;
                    font-weight: bold;
                    color: #2563eb;
                    margin-bottom: 15px;
                    padding-bottom: 5px;
                    border-bottom: 1px solid #ddd;
                }}
                .terms-content {{
                    margin: 15px 0;
                }}
                .footer {{
                    margin-top: 50px;
                    padding-top: 20px;
                    border-top: 1px solid #ddd;
                    text-align: center;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>BidVex Auction Platform</h1>
                <p style="font-size: 18px; font-weight: bold;">{listing.get('title', 'Auction')}</p>
                <p>Hosted by: {seller_name}</p>
                <p>Auction ID: {listing_id}</p>
            </div>
        """
        
        # Add English terms
        if terms_en:
            html_content += f"""
            <div class="section">
                <div class="section-title">Terms & Conditions (English)</div>
                <div class="terms-content">
                    {terms_en}
                </div>
            </div>
            """
        
        # Add French terms
        if terms_fr:
            html_content += f"""
            <div class="section">
                <div class="section-title">Termes et Conditions (Français)</div>
                <div class="terms-content">
                    {terms_fr}
                </div>
            </div>
            """
        
        html_content += """
            <div class="footer">
                <p>This document was generated by BidVex Auction Platform</p>
                <p>For questions, please contact the auctioneer listed above</p>
            </div>
        </body>
        </html>
        """
        
        # Create PDF
        pdf_dir = "/app/temp_pdfs"
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_filename = f"auction_terms_{listing_id}.pdf"
        pdf_path = os.path.join(pdf_dir, pdf_filename)
        
        # Generate PDF from HTML
        HTML(string=html_content).write_pdf(pdf_path)
        
        return FileResponse(
            path=pdf_path,
            filename=pdf_filename,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={pdf_filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating auction terms PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")

@api_router.post("/multi-item-listings/{listing_id}/lots/{lot_number}/bid")
async def bid_on_lot(listing_id: str, lot_number: int, data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    if listing["seller_id"] == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot bid on your own listing")
    
    amount = data.get("amount")
    bid_type = data.get("bid_type", "normal")  # normal, monster, auto
    lots = listing["lots"]
    
    lot_index = next((i for i, lot in enumerate(lots) if lot["lot_number"] == lot_number), None)
    if lot_index is None:
        raise HTTPException(status_code=404, detail="Lot not found")
    
    current_price = lots[lot_index]["current_price"]
    
    # Validate increment (skip for monster bids)
    if bid_type == "normal":
        min_increment = get_minimum_increment(listing, current_price)
        if amount < current_price + min_increment:
            raise HTTPException(
                status_code=400,
                detail=f"Bid must be at least ${current_price + min_increment:.2f} (minimum increment: ${min_increment:.2f})"
            )
    elif bid_type == "monster":
        # Validate monster bid eligibility
        tier = current_user.subscription_tier
        monster_bids_used = current_user.monster_bids_used.get(listing_id, 0)
        
        if tier == "free" and monster_bids_used >= 1:
            raise HTTPException(
                status_code=403,
                detail="Free tier allows only 1 Monster Bid per auction"
            )
        
        if amount <= current_price:
            raise HTTPException(status_code=400, detail="Monster Bid must be higher than current price")
    
    # Calculate minimum bid with helpful error message
    min_increment = get_minimum_increment(listing, current_price) if bid_type == "normal" else 1
    min_bid = current_price + min_increment
    
    if amount <= current_price:
        raise HTTPException(
            status_code=400, 
            detail=f"Your bid must be at least ${min_bid:.2f} to lead."
        )
    
    # Update current price
    lots[lot_index]["current_price"] = amount
    lots[lot_index]["highest_bidder_id"] = current_user.id
    
    # ========== ANTI-SNIPING LOGIC (2-Minute Rule) ==========
    # If bid is placed within final 2 minutes, extend by 2 minutes from TIME OF BID
    # UNLIMITED extensions - auction only ends when bidding activity truly stops
    ANTI_SNIPE_WINDOW = 120  # 2 minutes in seconds
    
    now = datetime.now(timezone.utc)
    lot_end_time_str = lots[lot_index].get("lot_end_time")
    extension_applied = False
    new_end_time = None
    extension_count = lots[lot_index].get("extension_count", 0)
    
    if lot_end_time_str:
        lot_end_time = datetime.fromisoformat(lot_end_time_str) if isinstance(lot_end_time_str, str) else lot_end_time_str
        time_remaining = (lot_end_time - now).total_seconds()
        
        # If within final 2 minutes, extend by 2 minutes from NOW (unlimited extensions)
        if 0 < time_remaining <= ANTI_SNIPE_WINDOW:
            # T_new = Time of Bid + 120 seconds
            new_end_time = now + timedelta(seconds=ANTI_SNIPE_WINDOW)
            lots[lot_index]["lot_end_time"] = new_end_time.isoformat()
            lots[lot_index]["extension_count"] = extension_count + 1
            extension_applied = True
            logger.info(f"⏰ Anti-sniping triggered: listing={listing_id}, lot={lot_number}, old_end={lot_end_time.isoformat()}, new_end={new_end_time.isoformat()}, extensions={extension_count + 1}")
    
    # Note: Cascading behavior is INDEPENDENT - Item 1 extension does NOT affect Item 2/3
    # Each lot maintains its own end time independently
    
    await db.multi_item_listings.update_one(
        {"id": listing_id},
        {"$set": {"lots": lots}}
    )
    
    # Broadcast time extension via WebSocket if applied
    if extension_applied and new_end_time:
        await manager.broadcast(listing_id, {
            'type': 'TIME_EXTENSION',
            'listing_id': listing_id,
            'lot_number': lot_number,
            'new_end_time': new_end_time.isoformat(),
            'extension_count': extension_count + 1,
            'reason': 'anti_sniping',
            'timestamp': now.isoformat()
        })
    
    bid = {
        "id": str(uuid.uuid4()),
        "listing_id": listing_id,
        "lot_number": lot_number,
        "bidder_id": current_user.id,
        "amount": amount,
        "bid_type": bid_type,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Create a copy of bid for database insertion
    bid_for_db = bid.copy()
    
    # Insert bid into database (MongoDB will add _id field to bid_for_db)
    await db.lot_bids.insert_one(bid_for_db)
    
    # Update monster bids used if applicable
    if bid_type == "monster":
        monster_bids_used_dict = current_user.monster_bids_used.copy()
        monster_bids_used_dict[listing_id] = monster_bids_used_dict.get(listing_id, 0) + 1
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {"monster_bids_used": monster_bids_used_dict}}
        )
    
    # Return response with clean bid data (original bid dict without MongoDB _id)
    response = {
        "message": "Bid placed successfully",
        "bid": bid,  # Original dict, not mutated by MongoDB
        "minimum_next_bid": current_price + get_minimum_increment(listing, amount) if bid_type == "normal" else None,
        "extension_applied": extension_applied,
        "extension_count": lots[lot_index].get("extension_count", 0)
    }
    
    # Include new end time if extension was applied
    if extension_applied and new_end_time:
        response["new_lot_end_time"] = new_end_time.isoformat()
        response["anti_sniping_message"] = "Auction extended by 2 minutes due to last-minute bidding activity."
    
    return response

@app.websocket("/ws/messages/{user_id}")
async def websocket_messages(websocket: WebSocket, user_id: str):
    await manager.connect_user(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        manager.disconnect_user(websocket, user_id)

# ========== REAL-TIME MESSAGING WEBSOCKET ==========
@app.websocket("/api/ws/messaging/{conversation_id}")
async def websocket_messaging(websocket: WebSocket, conversation_id: str, user_id: str = Query(None)):
    """
    Real-time WebSocket for messaging within a conversation.
    
    Features:
    - Instant message delivery (<200ms)
    - Typing indicators
    - Read receipts
    - Online/offline status
    - Message persistence
    
    Query params:
        user_id: The authenticated user's ID
    
    Message types (client -> server):
        SEND_MESSAGE: Send a new message
        TYPING_START: User started typing
        TYPING_STOP: User stopped typing
        MARK_READ: Mark messages as read
        PING: Heartbeat
    
    Message types (server -> client):
        NEW_MESSAGE: New message received
        TYPING_STATUS: Other user typing indicator
        READ_RECEIPT: Messages marked as read
        USER_STATUS: Online/offline status change
        CONNECTION_ESTABLISHED: Connection confirmed
        HEARTBEAT: Server heartbeat
        ERROR: Error message
    """
    if not user_id:
        await websocket.close(code=4001, reason="User ID required")
        return
    
    # Validate user has access to this conversation
    conversation = await db.conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conversation:
        await websocket.close(code=4004, reason="Conversation not found")
        return
    
    if user_id not in conversation.get("participants", []):
        await websocket.close(code=4003, reason="Not authorized for this conversation")
        return
    
    # Connect to conversation room
    await message_manager.connect(websocket, conversation_id, user_id)
    
    # Get other participant info
    other_user_id = [p for p in conversation["participants"] if p != user_id][0]
    other_user = await db.users.find_one({"id": other_user_id}, {"_id": 0, "name": 1, "picture": 1, "id": 1})
    
    # Get listing info if conversation has one
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
                "price": listing.get("current_price") or (listing.get("lots", [{}])[0].get("current_price") if listing.get("lots") else None)
            }
    
    # Send connection confirmation with initial state
    try:
        await websocket.send_json({
            "type": "CONNECTION_ESTABLISHED",
            "conversation_id": conversation_id,
            "other_user": other_user,
            "other_user_online": message_manager.is_user_in_conversation(conversation_id, other_user_id),
            "listing_info": listing_info,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Notify other user that this user is now online in this conversation
        await message_manager.send_to_conversation(
            conversation_id,
            {
                "type": "USER_STATUS",
                "user_id": user_id,
                "status": "online",
                "in_conversation": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            exclude_user=user_id
        )
        
    except Exception as e:
        logger.error(f"Error sending initial state: {str(e)}")
        return
    
    try:
        while True:
            # Receive message with timeout for heartbeat
            try:
                raw_message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                data = json.loads(raw_message)
                message_manager.update_online_status(user_id)
                
                msg_type = data.get("type")
                
                if msg_type == "SEND_MESSAGE":
                    # Create and persist message
                    content = data.get("content", "").strip()
                    if not content:
                        await websocket.send_json({"type": "ERROR", "message": "Message content required"})
                        continue
                    
                    message = Message(
                        conversation_id=conversation_id,
                        sender_id=user_id,
                        receiver_id=other_user_id,
                        listing_id=conversation.get("listing_id"),
                        content=content
                    )
                    
                    msg_dict = message.model_dump()
                    msg_dict["created_at"] = msg_dict["created_at"].isoformat()
                    await db.messages.insert_one(msg_dict)
                    
                    # Update conversation
                    await db.conversations.update_one(
                        {"id": conversation_id},
                        {"$set": {
                            "last_message": content[:100],
                            "last_message_at": datetime.now(timezone.utc).isoformat()
                        }}
                    )
                    
                    # Broadcast to other participant(s) in room
                    await message_manager.send_to_conversation(
                        conversation_id,
                        {
                            "type": "NEW_MESSAGE",
                            "message": msg_dict,
                            "sender": {
                                "id": user_id,
                                "name": (await db.users.find_one({"id": user_id}, {"name": 1})).get("name", "User")
                            },
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        },
                        exclude_user=user_id
                    )
                    
                    # Also send via global notification if user not in conversation
                    if not message_manager.is_user_in_conversation(conversation_id, other_user_id):
                        sender = await db.users.find_one({"id": user_id}, {"name": 1, "picture": 1})
                        await manager.send_to_user(other_user_id, {
                            "type": "new_message_notification",
                            "conversation_id": conversation_id,
                            "sender_name": sender.get("name", "Someone"),
                            "sender_picture": sender.get("picture"),
                            "preview": content[:50] + ("..." if len(content) > 50 else ""),
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                    
                    # Confirm to sender
                    await websocket.send_json({
                        "type": "MESSAGE_SENT",
                        "message_id": msg_dict["id"],
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    
                    # Clear typing status after sending
                    await message_manager.broadcast_typing_status(conversation_id, user_id, False)
                    
                    logger.info(f"💬 Message sent in conversation {conversation_id}: {user_id} -> {other_user_id}")
                    
                elif msg_type == "TYPING_START":
                    await message_manager.broadcast_typing_status(conversation_id, user_id, True)
                    
                elif msg_type == "TYPING_STOP":
                    await message_manager.broadcast_typing_status(conversation_id, user_id, False)
                    
                elif msg_type == "MARK_READ":
                    message_ids = data.get("message_ids", [])
                    if message_ids:
                        # Update messages in database
                        await db.messages.update_many(
                            {"id": {"$in": message_ids}, "receiver_id": user_id},
                            {"$set": {"is_read": True, "read_at": datetime.now(timezone.utc).isoformat()}}
                        )
                        # Broadcast read receipt
                        await message_manager.broadcast_read_receipt(conversation_id, user_id, message_ids)
                    
                elif msg_type == "PING":
                    await websocket.send_json({
                        "type": "PONG",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    
            except asyncio.TimeoutError:
                # Send heartbeat on timeout
                try:
                    await websocket.send_json({
                        "type": "HEARTBEAT",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                except:
                    break
                    
    except WebSocketDisconnect:
        logger.info(f"💬 WebSocket disconnected: user {user_id} from conversation {conversation_id}")
    except Exception as e:
        logger.error(f"💬 WebSocket error: {str(e)}")
    finally:
        # Clean up and notify others
        message_manager.disconnect(conversation_id, user_id)
        
        # Notify other user that this user went offline
        await message_manager.send_to_conversation(
            conversation_id,
            {
                "type": "USER_STATUS",
                "user_id": user_id,
                "status": "offline",
                "in_conversation": False,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            exclude_user=user_id
        )

@api_router.get("/conversations/{conversation_id}/online-status")
async def get_conversation_online_status(conversation_id: str, current_user: User = Depends(get_current_user)):
    """Get online status of users in a conversation."""
    conversation = await db.conversations.find_one({"id": conversation_id}, {"_id": 0})
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if current_user.id not in conversation.get("participants", []):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    online_users = message_manager.get_online_users_in_conversation(conversation_id)
    
    return {
        "conversation_id": conversation_id,
        "online_users": online_users,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@api_router.get("/admin/users")
async def admin_get_users(current_user: User = Depends(get_current_user), limit: int = 100, skip: int = 0):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    users = await db.users.find({}, {"_id": 0, "password": 0}).skip(skip).limit(limit).to_list(limit)
    return users

@api_router.put("/admin/users/{user_id}/status")
async def admin_update_user_status(user_id: str, data: Dict[str, str], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com") and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    await db.users.update_one({"id": user_id}, {"$set": {"status": data.get("status")}})
    return {"message": "User status updated"}

# ========== MARKETPLACE SETTINGS API ==========
@api_router.get("/marketplace/feature-flags")
async def get_public_feature_flags():
    """
    Public endpoint to get marketplace feature flags.
    Used by frontend to conditionally show/hide features like Buy Now and Multi-Lot access.
    Only exposes safe, non-sensitive settings.
    """
    settings = await get_marketplace_settings()
    return {
        "enable_buy_now": settings.get("enable_buy_now", True),
        "enable_anti_sniping": settings.get("enable_anti_sniping", True),
        "anti_sniping_window_minutes": settings.get("anti_sniping_window_minutes", 2),
        "minimum_bid_increment": settings.get("minimum_bid_increment", 1.0),
        "allow_all_users_multi_lot": settings.get("allow_all_users_multi_lot", True),
    }

@api_router.get("/admin/marketplace-settings")
async def get_admin_marketplace_settings(current_user: User = Depends(get_current_user)):
    """Get current marketplace settings (admin only)."""
    if current_user.role != "admin" and not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    settings = await get_marketplace_settings()
    return settings

@api_router.put("/admin/marketplace-settings")
async def update_marketplace_settings(
    settings_data: Dict,
    current_user: User = Depends(get_current_user)
):
    """Update marketplace settings (admin only). Changes take effect immediately."""
    if current_user.role != "admin" and not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get current settings for comparison
    current_settings = await get_marketplace_settings()
    
    # Validate settings with type and range checks
    allowed_fields = {
        "allow_all_users_multi_lot": {"type": bool},
        "require_approval_new_sellers": {"type": bool}, 
        "max_active_auctions_per_user": {"type": int, "min": 1, "max": 100},
        "max_lots_per_auction": {"type": int, "min": 1, "max": 500},
        "minimum_bid_increment": {"type": float, "min": 1.0},
        "enable_anti_sniping": {"type": bool},
        "anti_sniping_window_minutes": {"type": int, "min": 1, "max": 60},
        "enable_buy_now": {"type": bool}
    }
    
    # Filter and validate fields
    update_data = {}
    changes = []
    
    for key, value in settings_data.items():
        if key not in allowed_fields:
            continue
            
        field_rules = allowed_fields[key]
        expected_type = field_rules["type"]
        
        # Type validation
        if expected_type == bool and not isinstance(value, bool):
            raise HTTPException(status_code=400, detail=f"{key} must be a boolean")
        elif expected_type == int:
            if not isinstance(value, int) or isinstance(value, bool):
                raise HTTPException(status_code=400, detail=f"{key} must be an integer")
            if "min" in field_rules and value < field_rules["min"]:
                raise HTTPException(status_code=400, detail=f"{key} must be at least {field_rules['min']}")
            if "max" in field_rules and value > field_rules["max"]:
                raise HTTPException(status_code=400, detail=f"{key} must be at most {field_rules['max']}")
        elif expected_type == float:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise HTTPException(status_code=400, detail=f"{key} must be a number")
            if "min" in field_rules and value < field_rules["min"]:
                raise HTTPException(status_code=400, detail=f"{key} must be at least {field_rules['min']}")
        
        # Track changes for audit
        old_value = current_settings.get(key)
        if old_value != value:
            changes.append({
                "field": key,
                "old_value": old_value,
                "new_value": value
            })
        
        update_data[key] = value
    
    if not update_data:
        return current_settings  # No changes to make
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_data["updated_by"] = current_user.email
    
    # Upsert settings
    await db.settings.update_one(
        {"id": "marketplace_settings"},
        {"$set": update_data},
        upsert=True
    )
    
    # Log each change with detailed audit trail
    for change in changes:
        log_entry = {
            "id": str(uuid.uuid4()),
            "action": "MARKETPLACE_SETTINGS_UPDATE",
            "admin_id": current_user.id,
            "admin_email": current_user.email,
            "target_type": "settings",
            "target_id": "marketplace_settings",
            "field_changed": change["field"],
            "old_value": str(change["old_value"]),
            "new_value": str(change["new_value"]),
            "details": f"Changed {change['field']}: {change['old_value']} → {change['new_value']}",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.admin_logs.insert_one(log_entry)
    
    logger.info(f"📋 Marketplace settings updated by {current_user.email}: {[c['field'] for c in changes]}")
    
    # Return updated settings
    return await get_marketplace_settings()


@api_router.post("/admin/marketplace-settings/restore-defaults")
async def restore_marketplace_defaults(current_user: User = Depends(get_current_user)):
    """Restore marketplace settings to factory defaults (admin only)."""
    if current_user.role != "admin" and not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get current settings before reset for audit
    current_settings = await get_marketplace_settings()
    
    # Define hard-coded system defaults
    system_defaults = {
        "id": "marketplace_settings",
        "allow_all_users_multi_lot": True,
        "require_approval_new_sellers": False,
        "max_active_auctions_per_user": 20,
        "max_lots_per_auction": 50,
        "minimum_bid_increment": 1.0,
        "enable_anti_sniping": True,
        "anti_sniping_window_minutes": 2,
        "enable_buy_now": True,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": current_user.email
    }
    
    # Replace all settings with defaults
    await db.settings.replace_one(
        {"id": "marketplace_settings"},
        system_defaults,
        upsert=True
    )
    
    # Log the reset action with detailed before/after
    log_entry = {
        "id": str(uuid.uuid4()),
        "action": "MARKETPLACE_SETTINGS_RESET",
        "admin_id": current_user.id,
        "admin_email": current_user.email,
        "target_type": "settings",
        "target_id": "marketplace_settings",
        "details": "Restored all marketplace settings to factory defaults",
        "previous_settings": {k: v for k, v in current_settings.items() if k != "_id"},
        "new_settings": {k: v for k, v in system_defaults.items() if k != "_id"},
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.admin_logs.insert_one(log_entry)
    
    logger.info(f"⚠️ Marketplace settings RESET to defaults by {current_user.email}")
    
    return system_defaults

# ========== EMAIL TEMPLATE MANAGEMENT ENDPOINTS ==========

@api_router.get("/admin/email-templates")
async def get_admin_email_templates(current_user: User = Depends(get_current_user)):
    """Get all email templates with categories (admin only)."""
    if current_user.role != "admin" and not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    templates = await get_email_templates()
    
    # Count templates per category and build response
    template_dict = templates.get("templates", {})
    total_count = len(template_dict)
    
    # Group templates by category
    categorized = {}
    for cat_key, cat_info in EMAIL_TEMPLATE_CATEGORIES.items():
        cat_templates = []
        for base_key in cat_info["keys"]:
            en_key = f"{base_key}_en"
            fr_key = f"{base_key}_fr"
            if en_key in template_dict or fr_key in template_dict:
                cat_templates.append({
                    "key": base_key,
                    "name": base_key.replace("_", " ").title(),
                    "en_id": template_dict.get(en_key, ""),
                    "fr_id": template_dict.get(fr_key, ""),
                })
        
        categorized[cat_key] = {
            **cat_info,
            "templates": cat_templates,
            "count": len(cat_templates)
        }
    
    return {
        "id": templates.get("id"),
        "categories": categorized,
        "total_templates": total_count,
        "updated_at": templates.get("updated_at"),
        "updated_by": templates.get("updated_by")
    }

@api_router.put("/admin/email-templates")
async def update_email_templates(
    updates: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Update email template IDs (admin only)."""
    if current_user.role != "admin" and not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    templates = await get_email_templates()
    current_templates = templates.get("templates", {})
    
    # Validate and update templates
    updated_keys = []
    for key, new_id in updates.get("templates", {}).items():
        # Validate SendGrid template ID format (d- followed by 32 hex chars = 34 total)
        import re
        if new_id and not re.match(r'^d-[a-f0-9]{32}$', new_id):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid template ID format for '{key}'. Must be 'd-' followed by 32 hexadecimal characters."
            )
        
        old_id = current_templates.get(key, "")
        if old_id != new_id:
            current_templates[key] = new_id
            updated_keys.append(key)
            
            # Log the change to admin action logs
            await db.admin_action_logs.insert_one({
                "id": str(uuid.uuid4()),
                "admin_id": current_user.id,
                "admin_email": current_user.email,
                "action": "email_template_update",
                "target_type": "email_template",
                "target_id": key,
                "old_value": old_id,
                "new_value": new_id,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
    
    # Update database
    await db.email_settings.update_one(
        {"id": "email_templates"},
        {
            "$set": {
                "templates": current_templates,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": current_user.email
            }
        },
        upsert=True
    )
    
    return {
        "message": f"Updated {len(updated_keys)} template(s)",
        "updated_keys": updated_keys,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": current_user.email
    }

@api_router.get("/admin/email-templates/search")
async def search_email_templates(
    q: str = "",
    current_user: User = Depends(get_current_user)
):
    """Search email templates by name or ID (admin only)."""
    if current_user.role != "admin" and not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    templates = await get_email_templates()
    template_dict = templates.get("templates", {})
    
    query = q.lower()
    results = []
    
    for key, template_id in template_dict.items():
        if query in key.lower() or query in template_id.lower():
            # Find category for this template
            category = "unknown"
            base_key = "_".join(key.split("_")[:-1])  # Remove language suffix
            for cat_key, cat_info in EMAIL_TEMPLATE_CATEGORIES.items():
                if base_key in cat_info["keys"]:
                    category = cat_key
                    break
            
            results.append({
                "key": key,
                "template_id": template_id,
                "category": category,
                "name": key.replace("_", " ").title()
            })
    
    return {
        "query": q,
        "count": len(results),
        "results": results
    }

@api_router.get("/admin/email-templates/audit-log")
async def get_email_template_audit_log(
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Get audit log of email template changes (admin only)."""
    if current_user.role != "admin" and not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    logs = await db.admin_action_logs.find(
        {"action": "email_template_update"},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return logs

@api_router.get("/admin/reports")
async def admin_get_reports(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    reports = await db.reports.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return reports

@api_router.get("/admin/listings/pending")
async def admin_get_pending_listings(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    listings = await db.listings.find({"status": "pending"}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [Listing(**listing) for listing in listings]

@api_router.put("/admin/listings/{listing_id}/moderate")
async def admin_moderate_listing(listing_id: str, data: Dict[str, str], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    action = data.get("action")
    if action == "approve":
        await db.listings.update_one({"id": listing_id}, {"$set": {"status": "active"}})
    elif action == "reject":
        await db.listings.update_one({"id": listing_id}, {"$set": {"status": "rejected"}})
    elif action == "remove":
        await db.listings.delete_one({"id": listing_id})
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    return {"message": f"Listing {action}d successfully"}

@api_router.get("/admin/transactions")
async def admin_get_transactions(current_user: User = Depends(get_current_user), limit: int = 50):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    transactions = await db.payment_transactions.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return transactions

@api_router.get("/admin/analytics")
async def admin_get_analytics(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    active_listings = await db.listings.count_documents({"status": "active"})
    total_users = await db.users.count_documents({})
    
    # Calculate total revenue from paid transactions
    paid_transactions = await db.payment_transactions.find({"payment_status": "paid"}, {"_id": 0, "amount": 1}).to_list(1000)
    total_revenue = sum([tx.get("amount", 0) for tx in paid_transactions])
    
    return {
        "active_listings": active_listings,
        "total_users": total_users,
        "total_revenue": total_revenue
    }

# ============================================
# SPRINT 1: OPERATIONS CONTROL ENDPOINTS
# ============================================

# PROMOTION MANAGEMENT
@api_router.get("/admin/promotions")
async def admin_get_promotions(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    promotions = await db.promotions.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return promotions

@api_router.post("/admin/promotions/create")
async def admin_create_promotion(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    promotion = {
        "id": str(uuid.uuid4()),
        "listing_id": data.get("listing_id"),
        "promotion_type": data.get("promotion_type"),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "end_date": data.get("end_date")
    }
    await db.promotions.insert_one(promotion)
    await db.listings.update_one({"id": data.get("listing_id")}, {"$set": {"is_promoted": True}})
    return promotion

@api_router.delete("/admin/promotions/{promotion_id}")
async def admin_delete_promotion(promotion_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    promotion = await db.promotions.find_one({"id": promotion_id})
    if promotion:
        await db.listings.update_one({"id": promotion.get("listing_id")}, {"$set": {"is_promoted": False}})
        await db.promotions.delete_one({"id": promotion_id})
    return {"message": "Promotion deleted"}

@api_router.put("/admin/listings/{listing_id}/feature")
async def admin_feature_listing(listing_id: str, data: Dict[str, bool], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    is_featured = data.get("is_featured", False)
    await db.listings.update_one({"id": listing_id}, {"$set": {"is_featured": is_featured}})
    return {"message": f"Listing {'featured' if is_featured else 'unfeatured'}"}

# CATEGORY MANAGEMENT
@api_router.post("/admin/categories")
async def admin_create_category(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    category = {
        "id": str(uuid.uuid4()),
        "name_en": data.get("name_en"),
        "name_fr": data.get("name_fr"),
        "icon": data.get("icon", "📦"),
        "order": data.get("order", 0),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.categories.insert_one(category)
    return category

@api_router.put("/admin/categories/{category_id}")
async def admin_update_category(category_id: str, data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.categories.update_one({"id": category_id}, {"$set": data})
    return {"message": "Category updated"}

@api_router.delete("/admin/categories/{category_id}")
async def admin_delete_category(category_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.categories.delete_one({"id": category_id})
    return {"message": "Category deleted"}

# AUCTION LIFECYCLE CONTROL
@api_router.get("/admin/auctions")
async def admin_get_auctions(status: str = None, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = {}
    if status:
        query["status"] = status
    
    listings = await db.listings.find(query, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    return [Listing(**listing) for listing in listings]

@api_router.put("/admin/auctions/{listing_id}/pause")
async def admin_pause_auction(listing_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.listings.update_one({"id": listing_id}, {"$set": {"status": "paused"}})
    return {"message": "Auction paused"}

@api_router.put("/admin/auctions/{listing_id}/resume")
async def admin_resume_auction(listing_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.listings.update_one({"id": listing_id}, {"$set": {"status": "active"}})
    return {"message": "Auction resumed"}

@api_router.put("/admin/auctions/{listing_id}/extend")
async def admin_extend_auction(listing_id: str, data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    new_end_date = data.get("new_end_date")
    await db.listings.update_one({"id": listing_id}, {"$set": {"auction_end_date": new_end_date}})
    return {"message": "Auction extended"}

@api_router.delete("/admin/auctions/{listing_id}/cancel")
async def admin_cancel_auction(listing_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.listings.update_one({"id": listing_id}, {"$set": {"status": "cancelled"}})
    return {"message": "Auction cancelled"}

# AFFILIATE PROGRAM MANAGEMENT
@api_router.get("/admin/affiliates")
async def admin_get_affiliates(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    affiliates = await db.affiliates.find({}, {"_id": 0}).to_list(100)
    return affiliates

@api_router.put("/admin/users/{user_id}/affiliate")
async def admin_set_affiliate_status(user_id: str, data: Dict[str, bool], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    is_affiliate = data.get("is_affiliate", False)
    if is_affiliate:
        affiliate_code = str(uuid.uuid4())[:8]
        await db.affiliates.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "affiliate_code": affiliate_code,
            "total_earnings": 0.0,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    else:
        await db.affiliates.delete_one({"user_id": user_id})
    
    return {"message": f"Affiliate status {'enabled' if is_affiliate else 'disabled'}"}

@api_router.get("/admin/affiliate/payouts")
async def admin_get_payout_requests(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    payouts = await db.payout_requests.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return payouts

@api_router.put("/admin/affiliate/payouts/{payout_id}/approve")
async def admin_approve_payout(payout_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.payout_requests.update_one({"id": payout_id}, {"$set": {"status": "approved"}})
    return {"message": "Payout approved"}

# ============================================
# SPRINT 2: MODERATION & ANALYTICS ENDPOINTS
# ============================================

# ENHANCED USER MANAGEMENT
@api_router.get("/admin/users/filter")
async def admin_filter_users(account_type: str = None, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = {}
    if account_type:
        query["account_type"] = account_type
    
    users = await db.users.find(query, {"_id": 0, "password": 0}).to_list(200)
    return users

@api_router.put("/admin/users/{user_id}/verify")
async def admin_verify_user(user_id: str, data: Dict[str, bool], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    is_verified = data.get("is_verified", False)
    await db.users.update_one({"id": user_id}, {"$set": {"verified": is_verified, "verified_at": datetime.now(timezone.utc).isoformat()}})
    return {"message": f"User {'verified' if is_verified else 'unverified'}"}

@api_router.get("/admin/analytics/users")
async def admin_user_analytics(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    personal_users = await db.users.count_documents({"account_type": "personal"})
    business_users = await db.users.count_documents({"account_type": "business"})
    
    return {
        "personal": personal_users,
        "business": business_users,
        "total": personal_users + business_users
    }

# LOTS AUCTION MODERATION
@api_router.get("/admin/lots/pending")
async def admin_get_pending_lots(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    lots = await db.multi_item_listings.find({"status": "pending"}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return lots

@api_router.put("/admin/lots/{lot_id}/moderate")
async def admin_moderate_lot(lot_id: str, data: Dict[str, str], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    action = data.get("action")
    if action == "approve":
        await db.multi_item_listings.update_one({"id": lot_id}, {"$set": {"status": "active"}})
    elif action == "reject":
        await db.multi_item_listings.update_one({"id": lot_id}, {"$set": {"status": "rejected"}})
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    return {"message": f"Lot {action}d successfully"}

# REPORT ENHANCEMENTS
@api_router.put("/admin/reports/{report_id}/update")
async def admin_update_report(report_id: str, data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    update_data = {}
    if "status" in data:
        update_data["status"] = data["status"]
    if "admin_notes" in data:
        update_data["admin_notes"] = data["admin_notes"]
    if "assigned_to" in data:
        update_data["assigned_to"] = data["assigned_to"]
    if "resolution" in data:
        update_data["resolution"] = data["resolution"]
    
    await db.reports.update_one({"id": report_id}, {"$set": update_data})
    return {"message": "Report updated"}

@api_router.get("/admin/reports/filter")
async def admin_filter_reports(category: str = None, severity: str = None, status: str = None, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = {}
    if category:
        query["category"] = category
    if severity:
        query["severity"] = severity
    if status:
        query["status"] = status
    
    reports = await db.reports.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return reports

# ADVANCED ANALYTICS
@api_router.get("/admin/analytics/revenue")
async def admin_revenue_analytics(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get transactions from last 30 days grouped by date
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    transactions = await db.payment_transactions.find(
        {"payment_status": "paid", "created_at": {"$gte": thirty_days_ago.isoformat()}},
        {"_id": 0, "amount": 1, "created_at": 1}
    ).to_list(1000)
    
    # Group by date
    daily_revenue = {}
    for tx in transactions:
        date = tx["created_at"][:10]
        daily_revenue[date] = daily_revenue.get(date, 0) + tx.get("amount", 0)
    
    return [{"date": date, "revenue": revenue} for date, revenue in sorted(daily_revenue.items())]

@api_router.get("/admin/analytics/listings")
async def admin_listing_analytics(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    active = await db.listings.count_documents({"status": "active"})
    sold = await db.listings.count_documents({"status": "sold"})
    pending = await db.listings.count_documents({"status": "pending"})
    cancelled = await db.listings.count_documents({"status": "cancelled"})
    
    return {
        "active": active,
        "sold": sold,
        "pending": pending,
        "cancelled": cancelled
    }

# ============================================
# SPRINT 3: ADVANCED FEATURES ENDPOINTS
# ============================================

# MESSAGING OVERSIGHT
@api_router.get("/admin/messages/flagged")
async def admin_get_flagged_messages(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    messages = await db.messages.find({"flagged": True}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return messages

@api_router.delete("/admin/messages/{message_id}")
async def admin_delete_message(message_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.messages.delete_one({"id": message_id})
    return {"message": "Message deleted"}

@api_router.put("/admin/users/{user_id}/messaging")
async def admin_suspend_messaging(user_id: str, data: Dict[str, bool], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    messaging_suspended = data.get("suspended", False)
    await db.users.update_one({"id": user_id}, {"$set": {"messaging_suspended": messaging_suspended}})
    return {"message": f"Messaging {'suspended' if messaging_suspended else 'restored'}"}

# ADMIN ACTION LOGS
@api_router.post("/admin/logs")
async def admin_create_log(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    log = {
        "id": str(uuid.uuid4()),
        "admin_id": current_user.id,
        "admin_email": current_user.email,
        "action": data.get("action"),
        "target_type": data.get("target_type"),
        "target_id": data.get("target_id"),
        "details": data.get("details", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.admin_logs.insert_one(log)
    return log

@api_router.get("/admin/logs")
async def admin_get_logs(action_type: str = None, limit: int = 100, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = {}
    if action_type:
        query["action"] = action_type
    
    logs = await db.admin_logs.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return logs

# PLATFORM ANNOUNCEMENTS
@api_router.get("/admin/announcements")
async def admin_get_announcements(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    announcements = await db.announcements.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return announcements

@api_router.post("/admin/announcements")
async def admin_create_announcement(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    announcement = {
        "id": str(uuid.uuid4()),
        "title": data.get("title"),
        "message": data.get("message"),
        "target_audience": data.get("target_audience", "all"),
        "status": "active",
        "scheduled_for": data.get("scheduled_for"),
        "created_by": current_user.id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.announcements.insert_one(announcement)
    return announcement

@api_router.delete("/admin/announcements/{announcement_id}")
async def admin_delete_announcement(announcement_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.announcements.delete_one({"id": announcement_id})
    return {"message": "Announcement deleted"}

# ============================================
# TRUST & SAFETY SYSTEM - AI POWERED
# ============================================

# PHASE 1: TRUST SCORING & FRAUD DETECTION

async def calculate_trust_score(user_id: str) -> int:
    """Calculate user trust score (0-100)"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        return 0
    
    score = 50  # Base score
    
    # Account age bonus (max +15)
    if user.get("created_at"):
        account_age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(user["created_at"])).days
        score += min(15, account_age_days // 10)
    
    # Verification bonuses
    if user.get("email_verified"):
        score += 10
    if user.get("phone_verified"):
        score += 10
    
    # Transaction history bonus (max +20)
    transactions = await db.payment_transactions.count_documents({"user_id": user_id, "payment_status": "paid"})
    score += min(20, transactions * 2)
    
    # Report penalties
    reports_against = await db.reports.count_documents({"reported_user_id": user_id})
    score -= reports_against * 5
    
    # Completion rate bonus
    completed = await db.listings.count_documents({"seller_id": user_id, "status": "sold"})
    cancelled = await db.listings.count_documents({"seller_id": user_id, "status": "cancelled"})
    if completed + cancelled > 0:
        completion_rate = completed / (completed + cancelled)
        score += int(completion_rate * 10)
    
    return max(0, min(100, score))

@api_router.get("/admin/trust-safety/scores")
async def get_trust_scores(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
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

@api_router.get("/admin/trust-safety/fraud-flags")
async def get_fraud_flags(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
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

@api_router.get("/admin/trust-safety/collusion-patterns")
async def detect_collusion(current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
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

@api_router.post("/admin/trust-safety/verify-requirement")
async def enforce_verification_requirement(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    requirement_type = data.get("type")  # "email" or "phone"
    enabled = data.get("enabled", True)
    
    await db.platform_settings.update_one(
        {"setting_key": f"require_{requirement_type}_verification"},
        {"$set": {"value": enabled, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    
    return {"message": f"{requirement_type.capitalize()} verification requirement {'enabled' if enabled else 'disabled'}"}

# PHASE 2: AI INTEGRATION

EMERGENT_LLM_KEY = "sk-emergent-45818088307Fa1bB23"

@api_router.post("/admin/trust-safety/analyze-content")
async def analyze_content_ai(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    content = data.get("content")
    content_type = data.get("type", "text")  # "text" or "image"
    
    try:
        from emergentintegrations.openai import OpenAIChatIntegration
        
        openai_client = OpenAIChatIntegration(api_key=EMERGENT_LLM_KEY)
        
        prompt = f"""Analyze this content for scams, fraud, or policy violations.
        
Content: {content}

Provide a risk assessment with:
1. Risk Level (low/medium/high)
2. Detected Issues (list)
3. Recommended Action
4. Confidence Score (0-100)

Respond in JSON format."""

        response = openai_client.chat_completion(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        analysis = response.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        
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

@api_router.post("/admin/trust-safety/scan-listing")
async def scan_listing_ai(listing_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    try:
        from emergentintegrations.openai import OpenAIChatIntegration
        
        openai_client = OpenAIChatIntegration(api_key=EMERGENT_LLM_KEY)
        
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

        response = openai_client.chat_completion(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        analysis = response.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        
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

@api_router.post("/admin/trust-safety/scan-messages")
async def scan_messages_ai(conversation_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
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

@api_router.get("/admin/trust-safety/behavioral-analysis")
async def behavioral_analysis(user_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
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

@api_router.post("/admin/trust-safety/auto-action")
async def execute_auto_action(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    if not current_user.email.endswith("@admin.bazario.com"):
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

@api_router.post("/notifications")
async def create_notification(data: Dict[str, Any]):
    notification = {
        "id": str(uuid.uuid4()),
        "user_id": data.get("user_id"),
        "type": data.get("type"),
        "title": data.get("title"),
        "content": data.get("content"),
        "link": data.get("link"),
        "is_read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.notifications.insert_one(notification)
    await manager.send_to_user(data.get("user_id"), {"type": "notification", "data": notification})
    return notification

@api_router.get("/notifications")
async def get_notifications(current_user: User = Depends(get_current_user), limit: int = 50):
    notifications = await db.notifications.find(
        {"user_id": current_user.id},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return notifications

@api_router.put("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_user: User = Depends(get_current_user)):
    await db.notifications.update_one(
        {"id": notification_id, "user_id": current_user.id},
        {"$set": {"is_read": True}}
    )
    return {"message": "Notification marked as read"}

@api_router.post("/promotions")
async def create_promotion(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    listing_id = data.get("listing_id")
    if not listing_id:
        raise HTTPException(status_code=400, detail="listing_id is required")
    
    # Verify listing exists and belongs to user
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    if listing["seller_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to promote this listing")
    
    promotion_id = str(uuid.uuid4())
    current_time = datetime.now(timezone.utc).isoformat()
    
    promotion_doc = {
        "id": promotion_id,
        "listing_id": listing_id,
        "seller_id": current_user.id,
        "promotion_type": data.get("promotion_type"),
        "price": data.get("price"),
        "start_date": current_time,
        "end_date": data.get("end_date"),
        "targeting": data.get("targeting", {}),
        "impressions": 0,
        "clicks": 0,
        "status": "pending",
        "payment_status": "pending",
        "created_at": current_time
    }
    
    await db.promotions.insert_one(promotion_doc)
    
    # Return a clean response without MongoDB fields
    return {
        "id": promotion_id,
        "listing_id": listing_id,
        "seller_id": current_user.id,
        "promotion_type": data.get("promotion_type"),
        "price": data.get("price"),
        "start_date": current_time,
        "end_date": data.get("end_date"),
        "targeting": data.get("targeting", {}),
        "impressions": 0,
        "clicks": 0,
        "status": "pending",
        "payment_status": "pending",
        "created_at": current_time
    }

@api_router.get("/promotions/my")
async def get_my_promotions(current_user: User = Depends(get_current_user)):
    promotions = await db.promotions.find(
        {"seller_id": current_user.id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return promotions


# Watchlist Endpoints
@api_router.post("/watchlist/add")
async def add_to_watchlist(
    item_id: str,
    item_type: str = "listing",  # 'listing', 'auction', 'lot'
    current_user: User = Depends(get_current_user)
):
    """Add an item to user's watchlist (listing, auction, or lot)"""
    try:
        # Validate item_type
        if item_type not in ['listing', 'auction', 'lot']:
            raise HTTPException(status_code=400, detail="Invalid item_type. Must be 'listing', 'auction', or 'lot'")
        
        # Check if item exists based on type
        if item_type == 'listing':
            item = await db.listings.find_one({"id": item_id}, {"_id": 0})
            if not item:
                raise HTTPException(status_code=404, detail="Listing not found")
        elif item_type == 'auction':
            item = await db.multi_item_listings.find_one({"id": item_id}, {"_id": 0})
            if not item:
                raise HTTPException(status_code=404, detail="Auction not found")
        elif item_type == 'lot':
            # For lots, check if the parent auction exists
            # Extract auction_id from lot reference (format: auction_id:lot_number or just use item_id as reference)
            item = await db.multi_item_listings.find_one(
                {"lots.lot_number": {"$exists": True}}, 
                {"_id": 0}
            )
            if not item:
                raise HTTPException(status_code=404, detail="Lot not found")
        
        # Check if already in watchlist
        existing = await db.watchlist.find_one({
            "user_id": current_user.id,
            "item_id": item_id,
            "item_type": item_type
        })
        
        if existing:
            return {"message": "Already in watchlist", "already_added": True}
        
        # Add to watchlist
        watchlist_item = {
            "id": str(uuid.uuid4()),
            "user_id": current_user.id,
            "item_id": item_id,
            "item_type": item_type,
            "added_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.watchlist.insert_one(watchlist_item)
        return {"message": "Added to watchlist", "success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding to watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to add to watchlist")

@api_router.post("/watchlist/remove")
async def remove_from_watchlist(
    item_id: str,
    item_type: str = "listing",
    current_user: User = Depends(get_current_user)
):
    """Remove an item from user's watchlist"""
    try:
        result = await db.watchlist.delete_one({
            "user_id": current_user.id,
            "item_id": item_id,
            "item_type": item_type
        })
        
        if result.deleted_count == 0:
            return {"message": "Item not in watchlist", "success": False}
        
        return {"message": "Removed from watchlist", "success": True}
        
    except Exception as e:
        logger.error(f"Error removing from watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to remove from watchlist")

@api_router.get("/watchlist")
async def get_watchlist(current_user: User = Depends(get_current_user)):
    """Get user's watchlist with item details (listings, auctions, and lots)"""
    try:
        # Get all watchlist items for user
        watchlist_items = await db.watchlist.find(
            {"user_id": current_user.id},
            {"_id": 0}
        ).sort("added_at", -1).to_list(200)
        
        if not watchlist_items:
            return {
                "listings": [],
                "auctions": [],
                "lots": [],
                "total": 0
            }
        
        # Separate by type
        listing_items = [item for item in watchlist_items if item.get("item_type", "listing") == "listing"]
        auction_items = [item for item in watchlist_items if item.get("item_type") == "auction"]
        lot_items = [item for item in watchlist_items if item.get("item_type") == "lot"]
        
        result = {
            "listings": [],
            "auctions": [],
            "lots": [],
            "total": len(watchlist_items)
        }
        
        # Fetch listings
        if listing_items:
            listing_ids = [item.get("item_id") or item.get("listing_id") for item in listing_items]
            listings = await db.listings.find(
                {"id": {"$in": listing_ids}, "status": {"$ne": "deleted"}},
                {"_id": 0}
            ).to_list(100)
            
            listings_map = {listing["id"]: listing for listing in listings}
            
            for item in listing_items:
                item_id = item.get("item_id") or item.get("listing_id")
                listing = listings_map.get(item_id)
                if listing:
                    result["listings"].append({
                        **listing,
                        "watchlist_added_at": item["added_at"],
                        "watchlist_type": "listing"
                    })
        
        # Fetch auctions
        if auction_items:
            auction_ids = [item["item_id"] for item in auction_items]
            auctions = await db.multi_item_listings.find(
                {"id": {"$in": auction_ids}, "status": {"$ne": "deleted"}},
                {"_id": 0}
            ).to_list(100)
            
            auctions_map = {auction["id"]: auction for auction in auctions}
            
            for item in auction_items:
                auction = auctions_map.get(item["item_id"])
                if auction:
                    result["auctions"].append({
                        **auction,
                        "watchlist_added_at": item["added_at"],
                        "watchlist_type": "auction"
                    })
        
        # Fetch lots (need to find parent auction and specific lot)
        if lot_items:
            # lot_items contain item_id in format "auction_id:lot_number"
            for item in lot_items:
                item_id = item["item_id"]
                # Parse auction_id and lot_number
                if ":" in item_id:
                    auction_id, lot_number = item_id.split(":")
                    lot_number = int(lot_number)
                    
                    # Find the auction
                    auction = await db.multi_item_listings.find_one(
                        {"id": auction_id},
                        {"_id": 0}
                    )
                    
                    if auction:
                        # Find the specific lot
                        lot = next((l for l in auction.get("lots", []) if l.get("lot_number") == lot_number), None)
                        if lot:
                            result["lots"].append({
                                "auction_id": auction_id,
                                "auction_title": auction.get("title"),
                                "lot": lot,
                                "watchlist_added_at": item["added_at"],
                                "watchlist_type": "lot"
                            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch watchlist")

@api_router.get("/watchlist/check/{listing_id}")
async def check_watchlist_status(listing_id: str, current_user: User = Depends(get_current_user)):
    """Check if a listing is in user's watchlist"""
    try:
        exists = await db.watchlist.find_one({
            "user_id": current_user.id,
            "listing_id": listing_id
        })
        
        return {"in_watchlist": exists is not None}
        
    except Exception as e:
        logger.error(f"Error checking watchlist status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check watchlist status")

# Lot Watching Endpoints (for multi-item listings)
@api_router.post("/lots/watch")
async def watch_lot(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    """Add a specific lot to user's watched lots"""
    try:
        listing_id = data.get("listing_id")
        lot_number = data.get("lot_number")
        
        if not listing_id or lot_number is None:
            raise HTTPException(status_code=400, detail="listing_id and lot_number are required")
        
        # Check if already watching
        existing = await db.watched_lots.find_one({
            "user_id": current_user.id,
            "listing_id": listing_id,
            "lot_number": lot_number
        })
        
        if existing:
            return {"message": "Already watching this lot", "already_watching": True}
        
        # Add to watched lots
        watched_item = {
            "id": str(uuid.uuid4()),
            "user_id": current_user.id,
            "listing_id": listing_id,
            "lot_number": lot_number,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.watched_lots.insert_one(watched_item)
        return {"message": "Lot added to watched list", "success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error watching lot: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to watch lot")

@api_router.post("/lots/unwatch")
async def unwatch_lot(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    """Remove a specific lot from user's watched lots"""
    try:
        listing_id = data.get("listing_id")
        lot_number = data.get("lot_number")
        
        if not listing_id or lot_number is None:
            raise HTTPException(status_code=400, detail="listing_id and lot_number are required")
        
        result = await db.watched_lots.delete_one({
            "user_id": current_user.id,
            "listing_id": listing_id,
            "lot_number": lot_number
        })
        
        if result.deleted_count == 0:
            return {"message": "Lot not in watched list", "success": False}
        
        return {"message": "Lot removed from watched list", "success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unwatching lot: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to unwatch lot")

@api_router.get("/lots/watched")
async def get_watched_lots(current_user: User = Depends(get_current_user)):
    """Get all lots the user is watching"""
    try:
        watched = await db.watched_lots.find(
            {"user_id": current_user.id},
            {"_id": 0}
        ).to_list(1000)
        
        return {"watched_lots": watched}
        
    except Exception as e:
        logger.error(f"Error fetching watched lots: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch watched lots")

@api_router.get("/lots/watched/check")
async def check_lot_watch_status(listing_id: str, lot_number: int, current_user: User = Depends(get_current_user)):
    """Check if user is watching a specific lot"""
    try:
        exists = await db.watched_lots.find_one({
            "user_id": current_user.id,
            "listing_id": listing_id,
            "lot_number": lot_number
        })
        
        return {"is_watching": exists is not None}
        
    except Exception as e:
        logger.error(f"Error checking lot watch status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check watch status")


# Recently Viewed Tracking Endpoints
@api_router.post("/tracking/view/{listing_id}")
async def track_listing_view(listing_id: str, current_user: User = Depends(get_current_user)):
    """Track a listing view for logged-in users"""
    try:
        # Check if listing exists
        listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")
        
        # Check if already viewed recently (within last 24 hours)
        recent_view = await db.recently_viewed.find_one({
            "user_id": current_user.id,
            "listing_id": listing_id
        })
        
        current_time = datetime.now(timezone.utc).isoformat()
        
        if recent_view:
            # Update timestamp
            await db.recently_viewed.update_one(
                {"user_id": current_user.id, "listing_id": listing_id},
                {"$set": {"viewed_at": current_time}}
            )
        else:
            # Add new view record
            view_record = {
                "id": str(uuid.uuid4()),
                "user_id": current_user.id,
                "listing_id": listing_id,
                "viewed_at": current_time
            }
            await db.recently_viewed.insert_one(view_record)
        
        return {"message": "View tracked", "success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking view: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to track view")

@api_router.get("/tracking/recently-viewed")
async def get_recently_viewed(limit: int = 10, current_user: User = Depends(get_current_user)):
    """Get user's recently viewed listings"""
    try:
        # Get recently viewed records
        viewed_records = await db.recently_viewed.find(
            {"user_id": current_user.id},
            {"_id": 0}
        ).sort("viewed_at", -1).limit(limit).to_list(limit)
        
        if not viewed_records:
            return []
        
        # Get listing IDs
        listing_ids = [record["listing_id"] for record in viewed_records]
        
        # Fetch listing details
        listings = await db.listings.find(
            {"id": {"$in": listing_ids}, "status": {"$ne": "deleted"}},
            {"_id": 0}
        ).to_list(limit)
        
        # Create a map for quick lookup
        listings_map = {listing["id"]: listing for listing in listings}
        
        # Return listings in the order they were viewed
        result = []
        for record in viewed_records:
            listing = listings_map.get(record["listing_id"])
            if listing:
                result.append({
                    **listing,
                    "viewed_at": record["viewed_at"]
                })
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching recently viewed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch recently viewed")

# Carousel Data Endpoints
@api_router.get("/carousel/ending-soon")
async def get_ending_soon_listings(limit: int = 12):
    """Get listings ending soon (within next 24 hours)"""
    try:
        current_time = datetime.now(timezone.utc)
        twenty_four_hours_later = current_time + timedelta(hours=24)
        
        listings = await db.listings.find(
            {
                "status": "active",
                "auction_end_date": {
                    "$gte": current_time.isoformat(),
                    "$lte": twenty_four_hours_later.isoformat()
                }
            },
            {"_id": 0}
        ).sort("auction_end_date", 1).limit(limit).to_list(limit)
        
        return listings
        
    except Exception as e:
        logger.error(f"Error fetching ending soon listings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch ending soon listings")

@api_router.get("/carousel/featured")
async def get_featured_listings(limit: int = 12):
    """Get featured/promoted listings"""
    try:
        listings = await db.listings.find(
            {
                "status": "active",
                "is_promoted": True
            },
            {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        return listings
        
    except Exception as e:
        logger.error(f"Error fetching featured listings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch featured listings")


@api_router.get("/carousel/new-listings")
async def get_new_listings(limit: int = 12):
    """Get newest listings (created in last 7 days)"""
    try:
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        
        listings = await db.listings.find(
            {
                "status": "active",
                "created_at": {"$gte": seven_days_ago.isoformat()}
            },
            {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        return listings
        
    except Exception as e:
        logger.error(f"Error fetching new listings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch new listings")

@api_router.get("/carousel/recently-sold")
async def get_recently_sold(limit: int = 12):
    """Get recently sold items"""
    try:
        listings = await db.listings.find(
            {
                "status": "sold"
            },
            {"_id": 0}
        ).sort("sold_at", -1).limit(limit).to_list(limit)
        
        return listings
        
    except Exception as e:
        logger.error(f"Error fetching recently sold: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch recently sold")

@api_router.get("/stats/top-sellers")
async def get_top_sellers(limit: int = 10):
    pipeline = [
        {"$match": {"status": "sold"}},
        {"$group": {"_id": "$seller_id", "total_sales": {"$sum": "$current_price"}, "count": {"$sum": 1}}},
        {"$sort": {"total_sales": -1}},
        {"$limit": limit}
    ]
    results = await db.listings.aggregate(pipeline).to_list(limit)
    
    sellers = []
    for result in results:
        user = await db.users.find_one({"id": result["_id"]}, {"_id": 0, "password": 0})
        if user:
            sellers.append({
                "user": user,
                "total_sales": result["total_sales"],
                "items_sold": result["count"]
            })
    return sellers

@api_router.get("/stats/hot-items")
async def get_hot_items(limit: int = 10):
    listings = await db.listings.find(
        {"status": "active"},
        {"_id": 0}
    ).sort("views", -1).limit(limit).to_list(limit)
    
    for listing in listings:
        if isinstance(listing.get("created_at"), str):
            listing["created_at"] = datetime.fromisoformat(listing["created_at"])
        if isinstance(listing.get("auction_end_date"), str):
            listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])
    
    return [Listing(**listing) for listing in listings]

@api_router.get("/")
async def root():
    return {"message": "Bazario API v1.0"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

# ==================== INVOICE GENERATION ====================


def generate_pdf_from_html(html_content: str, pdf_path: Path):
    """Lazy import WeasyPrint and generate PDF"""
    try:
        from weasyprint import HTML
        HTML(string=html_content).write_pdf(pdf_path)
    except Exception as e:
        logger.error(f"PDF generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

# WeasyPrint import moved to lazy loading to avoid startup issues
from invoice_templates import lots_won_template
import os


def detect_currency_from_location(city: str = None, region: str = None, country: str = None) -> str:
    """
    Detect currency based on user location
    
    Args:
        city: City name
        region: Region/state/province
        country: Country name
    
    Returns:
        'CAD' for Canada, 'USD' for United States, defaults to 'CAD'
    """
    # Check country first
    if country:
        country_lower = country.lower()
        if 'united states' in country_lower or 'usa' in country_lower or 'us' == country_lower:
            return 'USD'
        if 'canada' in country_lower:
            return 'CAD'
    
    # Check region for Canadian provinces
    canadian_provinces = [
        'alberta', 'british columbia', 'manitoba', 'new brunswick', 
        'newfoundland', 'labrador', 'northwest territories', 'nova scotia',
        'nunavut', 'ontario', 'prince edward island', 'quebec', 'saskatchewan', 'yukon',
        'ab', 'bc', 'mb', 'nb', 'nl', 'nt', 'ns', 'nu', 'on', 'pe', 'qc', 'sk', 'yt'
    ]
    
    # Check region for US states
    us_states = [
        'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
        'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho',
        'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
        'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota', 'mississippi',
        'missouri', 'montana', 'nebraska', 'nevada', 'new hampshire', 'new jersey',
        'new mexico', 'new york', 'north carolina', 'north dakota', 'ohio', 'oklahoma',
        'oregon', 'pennsylvania', 'rhode island', 'south carolina', 'south dakota',
        'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington',
        'west virginia', 'wisconsin', 'wyoming'
    ]
    
    if region:
        region_lower = region.lower()
        if any(province in region_lower for province in canadian_provinces):
            return 'CAD'
        if any(state in region_lower for state in us_states):
            return 'USD'
    
    # Default to CAD
    return 'CAD'

def get_tax_rates_for_currency(currency: str) -> Dict[str, float]:
    """
    Get applicable tax rates based on currency
    
    Args:
        currency: 'CAD' or 'USD'
    
    Returns:
        Dict with tax_rate_gst and tax_rate_qst
    """
    if currency == 'CAD':
        return {
            "tax_rate_gst": 5.0,
            "tax_rate_qst": 9.975
        }
    else:  # USD
        return {
            "tax_rate_gst": 0.0,
            "tax_rate_qst": 0.0
        }

def get_client_ip(request) -> str:
    """
    Extract client IP from request headers
    Handles proxy/load balancer forwarding
    """
    # Check common proxy headers
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        # Take first IP in chain (original client)
        return forwarded.split(',')[0].strip()
    
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip
    
    # Fallback to direct connection
    if request.client:
        return request.client.host
    
    return "127.0.0.1"

async def generate_paddle_number(auction_id: str) -> int:
    """Generate next paddle number for auction (starts at 5051)"""
    # Find highest paddle number for this auction
    highest = await db.paddle_numbers.find(
        {"auction_id": auction_id}
    ).sort("paddle_number", -1).limit(1).to_list(1)
    
    if highest:
        return highest[0]["paddle_number"] + 1
    return 5051  # Starting paddle number

async def generate_invoice_number(auction_id: str) -> str:
    """Generate invoice number: BV-{year}-{auction_id_short}-{sequence}"""
    year = datetime.now().year
    auction_short = auction_id[:8]  # First 8 chars of UUID
    
    # Count existing invoices for this auction
    count = await db.invoices.count_documents({"auction_id": auction_id})
    sequence = count + 1
    
    return f"BV-{year}-{auction_short}-{sequence:04d}"

@api_router.post("/invoices/lots-won/{auction_id}/{user_id}")
async def generate_lots_won_invoice(
    auction_id: str,
    user_id: str,
    lang: str = "en",
    current_user: User = Depends(get_current_user)
):
    """
    Generate Buyer Lots Won Summary PDF
    Requires admin privileges or matching user_id
    
    Query Parameters:
        lang: Language code ('en' or 'fr') - uses buyer's preference if not specified
    """
    # Check permissions (admin or own invoice)
    if current_user.account_type != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Fetch auction
    auction = await db.multi_item_listings.find_one({"id": auction_id})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    # Fetch buyer
    buyer = await db.users.find_one({"id": user_id})
    if not buyer:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Use buyer's preferred language if lang not specified
    if lang == "en" and buyer.get("preferred_language"):
        lang = buyer.get("preferred_language", "en")
    
    # Get or create paddle number
    paddle_record = await db.paddle_numbers.find_one({
        "auction_id": auction_id,
        "user_id": user_id
    })
    
    if not paddle_record:
        paddle_num = await generate_paddle_number(auction_id)
        paddle_record = {
            "id": str(uuid.uuid4()),
            "auction_id": auction_id,
            "user_id": user_id,
            "paddle_number": paddle_num,
            "assigned_at": datetime.now(timezone.utc).isoformat()
        }
        await db.paddle_numbers.insert_one(paddle_record)
    
    # Find lots won by this buyer
    # For MVP, we'll use lots from the auction that have bids from this user
    # In production, you'd track winning bids
    
    # For demo purposes, let's use first 3 lots as "won"
    lots_won = []
    for lot in auction['lots'][:3]:  # Demo: first 3 lots
        lots_won.append({
            "lot_number": lot['lot_number'],
            "title": lot['title'],
            "description": lot['description'],
            "quantity": lot['quantity'],
            "hammer_price": lot['current_price']  # Use current_price as hammer price
        })
    
    if not lots_won:
        raise HTTPException(status_code=400, detail="No lots won by this buyer")
    
    # Generate invoice number
    invoice_number = await generate_invoice_number(auction_id)
    
    # Prepare data for template
    template_data = {
        "invoice_number": invoice_number,
        "buyer": {
            "name": buyer['name'],
            "company_name": buyer.get('company_name'),
            "billing_address": buyer.get('billing_address', buyer.get('address')),
            "phone": buyer['phone'],
            "email": buyer['email']
        },
        "paddle_number": paddle_record['paddle_number'],
        "auction": {
            "title": auction['title'],
            "city": auction['city'],
            "region": auction['region'],
            "location": auction.get('location'),
            "auction_end_date": datetime.fromisoformat(auction['auction_end_date']) if isinstance(auction['auction_end_date'], str) else auction['auction_end_date']
        },
        "lots": lots_won,
        "premium_percentage": auction.get('premium_percentage', 5.0),
        "tax_rate_gst": auction.get('tax_rate_gst', 5.0),
        "tax_rate_qst": auction.get('tax_rate_qst', 9.975),
        "payment_deadline": "Within 3 business days",
        "currency": auction.get('currency', 'CAD')  # Include auction currency
    }
    
    # Generate HTML
    # Generate bilingual HTML
    try:
        from invoice_templates_bilingual import lots_won_template as lots_won_bilingual
        html_content = lots_won_bilingual(template_data, lang=lang)
    except ImportError:
        # Fallback to original template if bilingual not available
        html_content = lots_won_template(template_data)
    
    # Create user invoice directory
    invoice_dir = Path(f"/app/invoices/{user_id}")
    invoice_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate PDF
    pdf_filename = f"LotsWon_{auction_id}_{int(datetime.now().timestamp())}.pdf"
    pdf_path = invoice_dir / pdf_filename
    
    generate_pdf_from_html(html_content, pdf_path)
    
    # Save invoice record to database
    invoice_record = {
        "id": str(uuid.uuid4()),
        "invoice_number": invoice_number,
        "invoice_type": "lots_won",
        "user_id": user_id,
        "auction_id": auction_id,
        "pdf_path": str(pdf_path),
        "generated_date": datetime.now(timezone.utc).isoformat(),
        "status": "generated"
    }
    await db.invoices.insert_one(invoice_record)
    
    return {
        "success": True,
        "invoice_number": invoice_number,
        "pdf_path": str(pdf_path),
        "paddle_number": paddle_record['paddle_number'],
        "message": "Invoice generated successfully"
    }

@api_router.post("/invoices/payment-letter/{auction_id}/{user_id}")
async def generate_payment_letter(
    auction_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Generate Payment Letter PDF for buyer
    Requires admin privileges or matching user_id
    """
    # Check permissions
    if current_user.account_type != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Fetch auction
    auction = await db.multi_item_listings.find_one({"id": auction_id})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    # Fetch buyer
    buyer = await db.users.find_one({"id": user_id})
    if not buyer:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get paddle number
    paddle_record = await db.paddle_numbers.find_one({
        "auction_id": auction_id,
        "user_id": user_id
    })
    
    if not paddle_record:
        # Create if doesn't exist
        paddle_num = await generate_paddle_number(auction_id)
        paddle_record = {
            "id": str(uuid.uuid4()),
            "auction_id": auction_id,
            "user_id": user_id,
            "paddle_number": paddle_num,
            "assigned_at": datetime.now(timezone.utc).isoformat()
        }
        await db.paddle_numbers.insert_one(paddle_record)
    
    # Find lots won (demo: first 3 lots)
    lots_won = []
    for lot in auction['lots'][:3]:
        lots_won.append({
            "lot_number": lot['lot_number'],
            "title": lot['title'],
            "hammer_price": lot['current_price']
        })
    
    if not lots_won:
        raise HTTPException(status_code=400, detail="No lots won by this buyer")
    
    # Calculate totals (same as Lots Won Summary)
    hammer_total = sum(lot['hammer_price'] for lot in lots_won)
    premium_percentage = auction.get('premium_percentage', 5.0)
    premium_amount = hammer_total * (premium_percentage / 100)
    subtotal = hammer_total + premium_amount
    
    tax_rate_gst = auction.get('tax_rate_gst', 5.0)
    tax_rate_qst = auction.get('tax_rate_qst', 9.975)
    
    gst_on_hammer = hammer_total * (tax_rate_gst / 100)
    qst_on_hammer = hammer_total * (tax_rate_qst / 100)
    gst_on_premium = premium_amount * (tax_rate_gst / 100)
    qst_on_premium = premium_amount * (tax_rate_qst / 100)
    
    total_tax = gst_on_hammer + qst_on_hammer + gst_on_premium + qst_on_premium
    grand_total = subtotal + total_tax
    
    # Generate invoice number (reuse from lots won or create new)
    existing_invoice = await db.invoices.find_one({
        "auction_id": auction_id,
        "user_id": user_id,
        "invoice_type": "lots_won"
    })
    
    if existing_invoice:
        invoice_number = existing_invoice['invoice_number']
    else:
        invoice_number = await generate_invoice_number(auction_id)
    
    # Prepare data for template
    template_data = {
        "invoice_number": invoice_number,
        "buyer": {
            "name": buyer['name'],
            "company_name": buyer.get('company_name'),
            "billing_address": buyer.get('billing_address', buyer.get('address')),
            "phone": buyer['phone'],
            "email": buyer['email']
        },
        "paddle_number": paddle_record['paddle_number'],
        "auction": {
            "title": auction['title'],
            "city": auction['city'],
            "region": auction['region'],
            "auction_end_date": datetime.fromisoformat(auction['auction_end_date']) if isinstance(auction['auction_end_date'], str) else auction['auction_end_date']
        },
        "lots_count": len(lots_won),
        "hammer_total": hammer_total,
        "premium_amount": premium_amount,
        "premium_percentage": premium_percentage,
        "total_tax": total_tax,
        "grand_total": grand_total,
        "payment_deadline": auction.get('payment_deadline', 'Within 3 business days') if isinstance(auction.get('payment_deadline'), str) else "Within 3 business days"
    }
    
    # Generate HTML using bilingual template
    # Use buyer's preferred language if available
    lang = buyer.get('preferred_language', 'en')
    currency = auction.get('currency', 'CAD')
    template_data['currency'] = currency
    template_data['lots_count'] = len(lots_won)
    
    from invoice_templates_complete import payment_letter_template
    html_content = payment_letter_template(template_data, lang=lang)
    
    # Create user invoice directory
    invoice_dir = Path(f"/app/invoices/{user_id}")
    invoice_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate PDF
    pdf_filename = f"PaymentLetter_{auction_id}.pdf"
    pdf_path = invoice_dir / pdf_filename
    
    generate_pdf_from_html(html_content, pdf_path)
    
    # Save invoice record
    invoice_record = {
        "id": str(uuid.uuid4()),
        "invoice_number": invoice_number,
        "invoice_type": "payment_letter",
        "user_id": user_id,
        "auction_id": auction_id,
        "pdf_path": str(pdf_path),
        "generated_date": datetime.now(timezone.utc).isoformat(),
        "status": "generated"
    }
    await db.invoices.insert_one(invoice_record)
    
    return {
        "success": True,
        "invoice_number": invoice_number,
        "pdf_path": str(pdf_path),
        "paddle_number": paddle_record['paddle_number'],
        "amount_due": grand_total,
        "message": "Payment letter generated successfully"
    }

@api_router.get("/invoices/{user_id}")
async def get_user_invoices(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get all invoices for a user"""
    if current_user.account_type != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    invoices = await db.invoices.find({"user_id": user_id}, {"_id": 0}).to_list(100)
    
    for invoice in invoices:
        if isinstance(invoice.get('generated_date'), str):
            invoice['generated_date'] = datetime.fromisoformat(invoice['generated_date'])
    
    return invoices

@api_router.post("/invoices/seller-statement/{auction_id}/{seller_id}")
async def generate_seller_statement(
    auction_id: str,
    seller_id: str,
    current_user: User = Depends(get_current_user)
):
    """Generate Seller Statement PDF"""
    if current_user.account_type != "admin" and current_user.id != seller_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    auction = await db.multi_item_listings.find_one({"id": auction_id})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    seller = await db.users.find_one({"id": seller_id})
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    
    # Prepare lots with buyer info (demo: mark first 3 as sold)
    lots_data = []
    for i, lot in enumerate(auction['lots']):
        lot_info = {
            "lot_number": lot['lot_number'],
            "title": lot['title'],
            "description": lot['description'],
            "status": "sold" if i < 3 else "unsold"
        }
        
        if i < 3:  # Sold lots
            lot_info["hammer_price"] = lot['current_price']
            lot_info["buyer_name"] = "Test Buyer"
            lot_info["paddle_number"] = 5051 + i
        
        lots_data.append(lot_info)
    
    # Use seller's preferred language if available
    lang = seller.get('preferred_language', 'en')
    currency = auction.get('currency', 'CAD')
    
    from invoice_templates_complete import seller_statement_template
    template_data = {
        "seller": {
            "name": seller['name'],
            "company_name": seller.get('company_name'),
            "address": seller.get('address'),
            "email": seller['email'],
            "phone": seller['phone']
        },
        "auction": {
            "title": auction['title'],
            "city": auction['city'],
            "region": auction['region'],
            "auction_end_date": datetime.fromisoformat(auction['auction_end_date']) if isinstance(auction['auction_end_date'], str) else auction['auction_end_date']
        },
        "lots": lots_data,
        "commission_rate": auction.get('commission_rate', 0.0),
        "currency": currency,
        "statement_number": f"STMT-{auction_id[:8]}"
    }
    
    html_content = seller_statement_template(template_data, lang=lang)
    
    invoice_dir = Path(f"/app/invoices/{seller_id}")
    invoice_dir.mkdir(parents=True, exist_ok=True)
    
    pdf_filename = f"SellerStatement_{auction_id}.pdf"
    pdf_path = invoice_dir / pdf_filename
    
    generate_pdf_from_html(html_content, pdf_path)
    
    invoice_record = {
        "id": str(uuid.uuid4()),
        "invoice_number": f"STMT-{auction_id[:8]}",
        "invoice_type": "seller_statement",
        "user_id": seller_id,
        "auction_id": auction_id,
        "pdf_path": str(pdf_path),
        "generated_date": datetime.now(timezone.utc).isoformat(),
        "status": "generated"
    }
    await db.invoices.insert_one(invoice_record)
    
    return {
        "success": True,
        "pdf_path": str(pdf_path),
        "message": "Seller statement generated successfully"
    }

@api_router.post("/invoices/seller-receipt/{auction_id}/{seller_id}")
async def generate_seller_receipt(
    auction_id: str,
    seller_id: str,
    current_user: User = Depends(get_current_user)
):
    """Generate Seller Receipt PDF"""
    if current_user.account_type != "admin" and current_user.id != seller_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    auction = await db.multi_item_listings.find_one({"id": auction_id})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    seller = await db.users.find_one({"id": seller_id})
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    
    # Calculate totals (demo: first 3 lots sold)
    total_hammer = sum(lot['current_price'] for lot in auction['lots'][:3])
    
    # Use seller's preferred language if available
    lang = seller.get('preferred_language', 'en')
    currency = auction.get('currency', 'CAD')
    
    from invoice_templates_complete import seller_receipt_template
    template_data = {
        "receipt_number": f"RCPT-{auction_id[:8]}-{int(datetime.now().timestamp())}",
        "seller": {
            "name": seller['name'],
            "company_name": seller.get('company_name'),
            "address": seller.get('address'),
            "email": seller['email']
        },
        "auction": {
            "title": auction['title'],
            "auction_end_date": datetime.fromisoformat(auction['auction_end_date']) if isinstance(auction['auction_end_date'], str) else auction['auction_end_date']
        },
        "total_lots": len(auction['lots']),
        "lots_sold": 3,
        "total_hammer": total_hammer,
        "commission_rate": auction.get('commission_rate', 0.0),
        "tax_rate_gst": auction.get('tax_rate_gst', 0.0),
        "tax_rate_qst": auction.get('tax_rate_qst', 0.0),
        "payment_method": "Bank Transfer",
        "payment_date": "Within 5-7 business days",
        "currency": currency
    }
    
    html_content = seller_receipt_template(template_data, lang=lang)
    
    invoice_dir = Path(f"/app/invoices/{seller_id}")
    invoice_dir.mkdir(parents=True, exist_ok=True)
    
    pdf_filename = f"SellerReceipt_{auction_id}.pdf"
    pdf_path = invoice_dir / pdf_filename
    
    generate_pdf_from_html(html_content, pdf_path)
    
    invoice_record = {
        "id": str(uuid.uuid4()),
        "invoice_number": template_data['receipt_number'],
        "invoice_type": "seller_receipt",
        "user_id": seller_id,
        "auction_id": auction_id,
        "pdf_path": str(pdf_path),
        "generated_date": datetime.now(timezone.utc).isoformat(),
        "status": "generated"
    }
    await db.invoices.insert_one(invoice_record)
    
    return {
        "success": True,
        "pdf_path": str(pdf_path),
        "receipt_number": template_data['receipt_number'],
        "message": "Seller receipt generated successfully"
    }

@api_router.post("/invoices/commission-invoice/{auction_id}/{seller_id}")
async def generate_commission_invoice(
    auction_id: str,
    seller_id: str,
    current_user: User = Depends(get_current_user)
):
    """Generate Commission Invoice PDF (BidVex to Seller)"""
    if current_user.account_type != "admin" and current_user.id != seller_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    auction = await db.multi_item_listings.find_one({"id": auction_id})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    seller = await db.users.find_one({"id": seller_id})
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    
    # Calculate totals
    total_hammer = sum(lot['current_price'] for lot in auction['lots'][:3])
    commission_rate = auction.get('commission_rate', 0.0)
    commission_amount = total_hammer * (commission_rate / 100)
    
    # Calculate net payout
    tax_rate_gst = auction.get('tax_rate_gst', 5.0)
    tax_rate_qst = auction.get('tax_rate_qst', 9.975)
    gst = commission_amount * (tax_rate_gst / 100)
    qst = commission_amount * (tax_rate_qst / 100)
    net_payout = total_hammer - commission_amount - gst - qst
    
    invoice_number = f"BV-COMM-{datetime.now().year}-{auction_id[:8]}-0001"
    
    # Use seller's preferred language if available
    lang = seller.get('preferred_language', 'en')
    currency = auction.get('currency', 'CAD')
    
    from invoice_templates_complete import commission_invoice_template
    template_data = {
        "invoice_number": invoice_number,
        "seller": {
            "name": seller['name'],
            "company_name": seller.get('company_name'),
            "address": seller.get('address'),
            "email": seller['email'],
            "phone": seller['phone']
        },
        "auction": {
            "title": auction['title'],
            "auction_end_date": datetime.fromisoformat(auction['auction_end_date']) if isinstance(auction['auction_end_date'], str) else auction['auction_end_date']
        },
        "total_hammer": total_hammer,
        "lots_sold": 3,
        "commission_rate": commission_rate,
        "commission_amount": commission_amount,
        "tax_rate_gst": tax_rate_gst,
        "tax_rate_qst": tax_rate_qst,
        "net_payout": net_payout,
        "due_date": "Upon Receipt",
        "currency": currency
    }
    
    html_content = commission_invoice_template(template_data, lang=lang)
    
    invoice_dir = Path(f"/app/invoices/{seller_id}")
    invoice_dir.mkdir(parents=True, exist_ok=True)
    
    pdf_filename = f"CommissionInvoice_{auction_id}.pdf"
    pdf_path = invoice_dir / pdf_filename
    
    generate_pdf_from_html(html_content, pdf_path)
    
    invoice_record = {
        "id": str(uuid.uuid4()),
        "invoice_number": invoice_number,
        "invoice_type": "commission_invoice",
        "user_id": seller_id,
        "auction_id": auction_id,
        "pdf_path": str(pdf_path),
        "generated_date": datetime.now(timezone.utc).isoformat(),
        "status": "generated"
    }
    await db.invoices.insert_one(invoice_record)
    
    return {
        "success": True,
        "invoice_number": invoice_number,
        "pdf_path": str(pdf_path),
        "message": "Commission invoice generated successfully"
    }


# ==================== AUTO-SEND INVOICES ON AUCTION END ====================

from email_service import MockEmailService

@api_router.post("/auctions/{auction_id}/complete")
async def complete_auction_and_send_documents(
    auction_id: str,
    lang: str = "en",
    current_user: User = Depends(get_current_user)
):
    """
    Complete auction and automatically generate + send all documents
    
    Triggers when auction status changes to 'ended':
    - Generates all buyer and seller documents
    - Sends emails with PDF attachments (mock mode)
    - Updates invoice records with email tracking
    
    Query Parameters:
        lang: Language code for documents ('en' or 'fr')
    
    Requires admin privileges
    """
    if current_user.account_type != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    # Fetch auction
    auction = await db.multi_item_listings.find_one({"id": auction_id})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    seller_id = auction['seller_id']
    seller = await db.users.find_one({"id": seller_id})
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    
    # Initialize mock email service
    email_service = MockEmailService(db=db)
    
    results = {
        "auction_id": auction_id,
        "auction_title": auction['title'],
        "documents_generated": [],
        "emails_sent": [],
        "errors": []
    }
    
    # ===== SELLER DOCUMENTS =====
    try:
        # Calculate seller totals
        total_hammer = sum(lot['current_price'] for lot in auction['lots'][:3])  # Demo: first 3 sold
        lots_sold = 3
        commission_rate = auction.get('commission_rate', 0.0)
        commission_amount = total_hammer * (commission_rate / 100)
        net_payout = total_hammer - commission_amount
        
        seller_pdf_paths = {}
        
        # 1. Generate Seller Statement
        try:
            statement_response = await generate_seller_statement(auction_id, seller_id, current_user)
            seller_pdf_paths['statement'] = statement_response['pdf_path']
            results['documents_generated'].append('seller_statement')
        except Exception as e:
            results['errors'].append(f"Seller Statement: {str(e)}")
        
        # 2. Generate Seller Receipt
        try:
            receipt_response = await generate_seller_receipt(auction_id, seller_id, current_user)
            seller_pdf_paths['receipt'] = receipt_response['pdf_path']
            results['documents_generated'].append('seller_receipt')
        except Exception as e:
            results['errors'].append(f"Seller Receipt: {str(e)}")
        
        # 3. Generate Commission Invoice
        try:
            commission_response = await generate_commission_invoice(auction_id, seller_id, current_user)
            seller_pdf_paths['commission'] = commission_response['pdf_path']
            results['documents_generated'].append('commission_invoice')
        except Exception as e:
            results['errors'].append(f"Commission Invoice: {str(e)}")
        
        # Send seller email (mock)
        if seller_pdf_paths:
            email_sent = await email_service.send_seller_documents_email(
                recipient_email=seller['email'],
                recipient_name=seller['name'],
                auction_title=auction['title'],
                total_hammer=total_hammer,
                lots_sold=lots_sold,
                net_payout=net_payout,
                pdf_paths=seller_pdf_paths,
                lang=lang
            )
            
            if email_sent:
                results['emails_sent'].append({
                    "type": "seller_documents",
                    "recipient": seller['email'],
                    "documents": list(seller_pdf_paths.keys())
                })
                
                # Update invoice records with email tracking
                await db.invoices.update_many(
                    {
                        "auction_id": auction_id,
                        "user_id": seller_id,
                        "invoice_type": {"$in": ["seller_statement", "seller_receipt", "commission_invoice"]}
                    },
                    {
                        "$set": {
                            "email_sent": True,
                            "sent_timestamp": datetime.now(timezone.utc).isoformat(),
                            "recipient_email": seller['email']
                        }
                    }
                )
    
    except Exception as e:
        results['errors'].append(f"Seller documents error: {str(e)}")
    
    # ===== BUYER DOCUMENTS =====
    # Find all buyers (paddle numbers assigned to this auction)
    paddle_records = await db.paddle_numbers.find({"auction_id": auction_id}).to_list(100)
    
    for paddle_record in paddle_records:
        buyer_id = paddle_record['user_id']
        paddle_number = paddle_record['paddle_number']
        
        try:
            buyer = await db.users.find_one({"id": buyer_id})
            if not buyer:
                continue
            
            buyer_pdf_paths = {}
            
            # 1. Generate Lots Won Summary
            try:
                lots_won_response = await generate_lots_won_invoice(auction_id, buyer_id, lang, current_user)
                buyer_pdf_paths['lots_won'] = lots_won_response['pdf_path']
                results['documents_generated'].append(f'lots_won_{buyer_id[:8]}')
                total_due = lots_won_response.get('total_due', 0)
                invoice_number = lots_won_response.get('invoice_number', 'N/A')
            except Exception as e:
                results['errors'].append(f"Lots Won (Buyer {buyer_id[:8]}): {str(e)}")
                continue
            
            # 2. Generate Payment Letter
            try:
                payment_letter_response = await generate_payment_letter(auction_id, buyer_id, current_user)
                buyer_pdf_paths['payment_letter'] = payment_letter_response['pdf_path']
                results['documents_generated'].append(f'payment_letter_{buyer_id[:8]}')
            except Exception as e:
                results['errors'].append(f"Payment Letter (Buyer {buyer_id[:8]}): {str(e)}")
            
            # Send buyer email (mock)
            if buyer_pdf_paths:
                email_sent = await email_service.send_buyer_invoice_email(
                    recipient_email=buyer['email'],
                    recipient_name=buyer['name'],
                    auction_title=auction['title'],
                    invoice_number=invoice_number,
                    total_due=total_due,
                    paddle_number=paddle_number,
                    pdf_paths=buyer_pdf_paths,
                    lang=lang
                )
                
                if email_sent:
                    results['emails_sent'].append({
                        "type": "buyer_invoice",
                        "recipient": buyer['email'],
                        "paddle_number": paddle_number,
                        "documents": list(buyer_pdf_paths.keys())
                    })
                    
                    # Update invoice records with email tracking
                    await db.invoices.update_many(
                        {
                            "auction_id": auction_id,
                            "user_id": buyer_id,
                            "invoice_type": {"$in": ["lots_won", "payment_letter"]}
                        },
                        {
                            "$set": {
                                "email_sent": True,
                                "sent_timestamp": datetime.now(timezone.utc).isoformat(),
                                "recipient_email": buyer['email']
                            }
                        }
                    )
        
        except Exception as e:
            results['errors'].append(f"Buyer documents error (buyer {buyer_id[:8]}): {str(e)}")
    
    # Update auction status to 'ended'
    await db.multi_item_listings.update_one(
        {"id": auction_id},
        {"$set": {"status": "ended"}}
    )
    
    results['success'] = len(results['errors']) == 0
    results['summary'] = {
        "total_documents": len(results['documents_generated']),
        "total_emails": len(results['emails_sent']),
        "total_errors": len(results['errors'])
    }
    
    return results

@api_router.get("/email-logs")
async def get_email_logs(
    current_user: User = Depends(get_current_user)
):
    """
    Get all email logs (mock emails sent)
    Requires admin privileges
    """
    if current_user.account_type != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    email_logs = await db.email_logs.find({}, {"_id": 0}).to_list(100)
    return {
        "total": len(email_logs),
        "emails": email_logs
    }

# ==================== END INVOICE GENERATION ====================

# Include API router after all endpoints are defined


# ==================== CURRENCY APPEAL SYSTEM ====================

class CurrencyAppeal(BaseModel):
    """Currency enforcement appeal submission"""
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    requested_currency: str  # CAD or USD
    reason: str
    proof_documents: Optional[List[str]] = None  # URLs to uploaded documents
    current_location: Optional[str] = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "pending"  # pending, approved, rejected
    admin_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None

@api_router.post("/currency-appeal")
async def submit_currency_appeal(
    requested_currency: str,
    reason: str,
    proof_documents: Optional[List[str]] = None,
    current_location: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Submit an appeal to change currency when it's locked
    
    Returns:
        Success message with appeal ID
    """
    if requested_currency not in ["CAD", "USD"]:
        raise HTTPException(status_code=400, detail="Currency must be 'CAD' or 'USD'")
    
    if not current_user.currency_locked:
        raise HTTPException(status_code=400, detail="Currency is not locked, you can change it directly")
    
    appeal = CurrencyAppeal(
        user_id=current_user.id,
        requested_currency=requested_currency,
        reason=reason,
        proof_documents=proof_documents or [],
        current_location=current_location
    )
    
    appeal_dict = appeal.model_dump()
    appeal_dict["submitted_at"] = appeal_dict["submitted_at"].isoformat()
    
    await db.currency_appeals.insert_one(appeal_dict)
    
    return {
        "success": True,
        "message": "Your appeal has been submitted and will be reviewed by our team within 24-48 hours.",
        "appeal_id": appeal.id
    }

@api_router.get("/currency-appeals")
async def get_user_appeals(current_user: User = Depends(get_current_user)):
    """Get all appeals for current user"""
    appeals = await db.currency_appeals.find(
        {"user_id": current_user.id},
        {"_id": 0}
    ).sort("submitted_at", -1).to_list(10)
    
    return {"appeals": appeals}

@api_router.post("/admin/currency-appeals/{appeal_id}/review")
async def review_currency_appeal(
    appeal_id: str,
    status: str,
    admin_notes: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Admin endpoint to review and approve/reject currency appeals
    
    Args:
        appeal_id: The appeal ID to review
        status: 'approved' or 'rejected'
        admin_notes: Optional notes from admin
        
    Returns:
        Success message
    """
    if not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if status not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Status must be 'approved' or 'rejected'")
    
    appeal = await db.currency_appeals.find_one({"id": appeal_id})
    if not appeal:
        raise HTTPException(status_code=404, detail="Appeal not found")
    
    # Update appeal status
    await db.currency_appeals.update_one(
        {"id": appeal_id},
        {
            "$set": {
                "status": status,
                "admin_notes": admin_notes,
                "reviewed_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    
    # If approved, unlock currency and update user
    if status == "approved":
        await db.users.update_one(
            {"id": appeal['user_id']},
            {
                "$set": {
                    "preferred_currency": appeal['requested_currency'],
                    "enforced_currency": appeal['requested_currency'],
                    "currency_locked": False
                }
            }
        )
    
    return {
        "success": True,
        "message": f"Appeal {status}",
        "appeal_id": appeal_id
    }

# ==================== SENDGRID WEBHOOKS ====================

@api_router.post("/webhooks/sendgrid")
async def sendgrid_webhook(request: Request):
    """
    SendGrid Event Webhook for email tracking.
    
    Tracks: delivered, opened, clicked, bounced, dropped, etc.
    Configure in SendGrid: Settings → Mail Settings → Event Webhook
    """
    try:
        events = await request.json()
        
        # Process each event
        for event in events:
            event_type = event.get('event')
            email = event.get('email')
            timestamp = event.get('timestamp')
            message_id = event.get('sg_message_id')
            
            # Log event for analytics
            logger.info(
                f"SendGrid event: type={event_type}, email={email}, "
                f"message_id={message_id}, timestamp={timestamp}"
            )
            
            # Store event in database for tracking
            await db.email_events.insert_one({
                "event_type": event_type,
                "email": email,
                "message_id": message_id,
                "timestamp": datetime.fromtimestamp(timestamp) if timestamp else None,
                "raw_event": event,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
            # Handle specific events
            if event_type == 'bounce':
                logger.warning(f"Email bounced: {email}, reason: {event.get('reason')}")
                # TODO: Mark email as invalid in user profile
            
            elif event_type == 'dropped':
                logger.error(f"Email dropped by SendGrid: {email}, reason: {event.get('reason')}")
            
        return {"status": "success", "processed": len(events)}
        
    except Exception as e:
        logger.exception(f"SendGrid webhook error: {str(e)}")
        # Return 200 to prevent SendGrid from retrying
        return {"status": "error", "message": str(e)}

# NOTE: api_router is included at the end of the file after all routes are defined

app.add_middleware(
    CORSMiddleware, allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"], allow_headers=["*"],
)

# ==================== WISHLIST ENDPOINTS ====================

@api_router.post("/wishlist")
async def add_to_wishlist(auction_id: str, lot_id: Optional[str] = None, current_user: User = Depends(get_current_user)):
    """Add auction or specific lot to user's wishlist"""
    try:
        # Check if already in wishlist
        existing = await db.wishlist.find_one({
            "user_id": current_user.id,
            "auction_id": auction_id,
            "lot_id": lot_id
        })
        
        if existing:
            return {"message": "Already in wishlist", "wishlist_id": existing["id"]}
        
        # Add to wishlist
        wishlist_item = Wishlist(
            user_id=current_user.id,
            auction_id=auction_id,
            lot_id=lot_id
        )
        await db.wishlist.insert_one(wishlist_item.model_dump())
        
        # Update auction wishlist count
        await db.multi_item_listings.update_one(
            {"id": auction_id},
            {"$inc": {"wishlist_count": 1}}
        )
        
        return {"message": "Added to wishlist", "wishlist_id": wishlist_item.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/wishlist/{auction_id}")
async def remove_from_wishlist(auction_id: str, current_user: User = Depends(get_current_user)):
    """Remove auction from user's wishlist"""
    try:
        result = await db.wishlist.delete_one({
            "user_id": current_user.id,
            "auction_id": auction_id
        })
        
        if result.deleted_count > 0:
            # Update auction wishlist count
            await db.multi_item_listings.update_one(
                {"id": auction_id},
                {"$inc": {"wishlist_count": -1}}
            )
            return {"message": "Removed from wishlist"}
        else:
            raise HTTPException(status_code=404, detail="Item not in wishlist")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/wishlist")
async def get_user_wishlist(current_user: User = Depends(get_current_user)):
    """Get user's wishlist with auction details"""
    try:
        wishlist_items = await db.wishlist.find({"user_id": current_user.id}).to_list(100)
        
        # Fetch auction details for each wishlist item
        auction_ids = list(set([item["auction_id"] for item in wishlist_items]))
        auctions = await db.multi_item_listings.find({"id": {"$in": auction_ids}}).to_list(100)
        
        # Map auctions by ID
        auctions_map = {auction["id"]: auction for auction in auctions}
        
        # Combine wishlist with auction data
        result = []
        for item in wishlist_items:
            auction = auctions_map.get(item["auction_id"])
            if auction:
                result.append({
                    "wishlist_id": item["id"],
                    "auction": auction,
                    "lot_id": item.get("lot_id"),
                    "added_at": item["created_at"]
                })
        
        return {"wishlist": result, "total": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== PREMIUM BIDDING FEATURES ====================

@api_router.post("/bids/monster")
async def place_monster_bid(listing_id: str, amount: float, current_user: User = Depends(get_current_user)):
    """Place a Monster Bid that overrides standard increments"""
    try:
        # Get listing
        listing = await db.listings.find_one({"id": listing_id})
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")
        
        # Check subscription tier
        tier = current_user.subscription_tier
        monster_bids_used = current_user.monster_bids_used.get(listing_id, 0)
        
        # Free tier: 1 monster bid per auction
        if tier == "free" and monster_bids_used >= 1:
            raise HTTPException(
                status_code=403,
                detail="Free tier allows only 1 Monster Bid per auction. Upgrade to Premium for unlimited Monster Bids."
            )
        
        # Check if amount is higher than current bid
        current_bid = listing.get("current_bid", listing.get("starting_price", 0))
        if amount <= current_bid:
            raise HTTPException(status_code=400, detail="Monster Bid must be higher than current bid")
        
        # Place the bid
        bid = Bid(
            listing_id=listing_id,
            bidder_id=current_user.id,
            amount=amount,
            bid_type="monster"
        )
        await db.bids.insert_one(bid.model_dump())
        
        # Update listing
        await db.listings.update_one(
            {"id": listing_id},
            {"$set": {"current_bid": amount, "highest_bidder": current_user.id}}
        )
        
        # Update user's monster bids used
        monster_bids_used_dict = current_user.monster_bids_used.copy()
        monster_bids_used_dict[listing_id] = monster_bids_used + 1
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {"monster_bids_used": monster_bids_used_dict}}
        )
        
        # Broadcast to websocket
        await manager.broadcast(listing_id, {
            "type": "monster_bid",
            "amount": amount,
            "bidder": current_user.name
        })
        
        return {
            "message": "Monster Bid placed successfully!",
            "bid_id": bid.id,
            "remaining_monster_bids": 0 if tier == "free" else "unlimited"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/bids/auto-bid")
async def setup_auto_bid(listing_id: str, max_bid: float, current_user: User = Depends(get_current_user)):
    """Setup Auto-Bid Bot (Premium/VIP only)"""
    try:
        # Check subscription tier
        if current_user.subscription_tier == "free":
            raise HTTPException(
                status_code=403,
                detail="Auto-Bid Bot is a Premium feature. Upgrade to Premium or VIP to use this feature."
            )
        
        # Get listing
        listing = await db.listings.find_one({"id": listing_id})
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")
        
        # Check if max_bid is valid
        current_bid = listing.get("current_bid", listing.get("starting_price", 0))
        if max_bid <= current_bid:
            raise HTTPException(status_code=400, detail="Max bid must be higher than current bid")
        
        # Check if user already has auto-bid for this listing
        existing = await db.auto_bids.find_one({
            "user_id": current_user.id,
            "listing_id": listing_id,
            "is_active": True
        })
        
        if existing:
            # Update existing auto-bid
            await db.auto_bids.update_one(
                {"id": existing["id"]},
                {"$set": {"max_bid": max_bid}}
            )
            return {"message": "Auto-Bid updated", "auto_bid_id": existing["id"]}
        else:
            # Create new auto-bid
            auto_bid = AutoBid(
                user_id=current_user.id,
                listing_id=listing_id,
                max_bid=max_bid
            )
            await db.auto_bids.insert_one(auto_bid.model_dump())
            return {"message": "Auto-Bid activated", "auto_bid_id": auto_bid.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/bids/auto-bid/{listing_id}")
async def deactivate_auto_bid(listing_id: str, current_user: User = Depends(get_current_user)):
    """Deactivate Auto-Bid Bot for a listing"""
    try:
        result = await db.auto_bids.update_one(
            {"user_id": current_user.id, "listing_id": listing_id, "is_active": True},
            {"$set": {"is_active": False}}
        )
        
        if result.modified_count > 0:
            return {"message": "Auto-Bid deactivated"}
        else:
            raise HTTPException(status_code=404, detail="No active Auto-Bid found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/bids/auto-bid")
async def get_user_auto_bids(current_user: User = Depends(get_current_user)):
    """Get user's active auto-bids"""
    try:
        auto_bids = await db.auto_bids.find({
            "user_id": current_user.id,
            "is_active": True
        }).to_list(100)
        
        return {"auto_bids": auto_bids, "total": len(auto_bids)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== AUCTION INCREMENT ENDPOINTS ====================

@api_router.get("/multi-item-listings/{listing_id}/increment-info")
async def get_increment_info(listing_id: str):
    """Get increment information for an auction"""
    try:
        listing = await db.multi_item_listings.find_one({"id": listing_id})
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")
        
        increment_option = listing.get("increment_option", "tiered")
        
        # Get increment schedule
        if increment_option == "simplified":
            schedule = [
                {"range": "$0-$100", "increment": "$1"},
                {"range": "$100-$1,000", "increment": "$5"},
                {"range": "$1,000-$10,000", "increment": "$25"},
                {"range": "$10,000+", "increment": "$100"}
            ]
        else:
            schedule = [
                {"range": "$0-$99.99", "increment": "$5"},
                {"range": "$100-$499.99", "increment": "$10"},
                {"range": "$500-$999.99", "increment": "$25"},
                {"range": "$1,000-$4,999.99", "increment": "$50"},
                {"range": "$5,000-$9,999.99", "increment": "$100"},
                {"range": "$10,000-$49,999.99", "increment": "$250"},
                {"range": "$50,000-$99,999.99", "increment": "$500"},
                {"range": "$100,000+", "increment": "$1,000"}
            ]
        
        return {
            "increment_option": increment_option,
            "schedule": schedule
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== SUBSCRIPTION MANAGEMENT ====================

@api_router.get("/subscription/status")
async def get_subscription_status(current_user: User = Depends(get_current_user)):
    """Get user's subscription status and features"""
    tier = current_user.subscription_tier
    
    features = {
        "free": {
            "tier": "Free",
            "monster_bids_per_auction": 1,
            "auto_bid_bot": False,
            "priority_notifications": False,
            "early_access": False
        },
        "premium": {
            "tier": "Premium",
            "monster_bids_per_auction": "unlimited",
            "auto_bid_bot": True,
            "priority_notifications": True,
            "early_access": False
        },
        "vip": {
            "tier": "VIP",
            "monster_bids_per_auction": "unlimited",
            "auto_bid_bot": True,
            "priority_notifications": True,
            "early_access": True
        }
    }
    
    return {
        "subscription_tier": tier,
        "subscription_status": current_user.subscription_status,
        "features": features.get(tier, features["free"]),
        "subscription_start_date": current_user.subscription_start_date,
        "subscription_end_date": current_user.subscription_end_date
    }

# ==================== SITE CONFIGURATION / BRANDING ====================

# Default site configuration
DEFAULT_SITE_CONFIG = {
    "id": "site_config",
    "branding": {
        "logo_url": None,  # Will store base64 or URL
        "logo_type": "default",  # "default", "uploaded", "url"
        "primary_color": "#3B82F6",  # Blue
        "secondary_color": "#10B981",  # Emerald
        "accent_color": "#8B5CF6",  # Purple
        "surface_color": "#F8FAFC",  # Light gray
        "font_family": "Inter",  # Google Font
    },
    "homepage_layout": {
        "sections": [
            {"id": "hero_banner", "name": "Hero Banner", "visible": True, "order": 0},
            {"id": "homepage_banner", "name": "Banner Carousel", "visible": True, "order": 1},
            {"id": "ending_soon", "name": "Ending Soon", "visible": True, "order": 2},
            {"id": "featured", "name": "Featured Auctions", "visible": True, "order": 3},
            {"id": "browse_items", "name": "Browse Individual Items", "visible": True, "order": 4},
            {"id": "new_listings", "name": "New Listings", "visible": True, "order": 5},
            {"id": "recently_sold", "name": "Recently Sold", "visible": True, "order": 6},
            {"id": "recently_viewed", "name": "Recently Viewed", "visible": True, "order": 7},
            {"id": "hot_items", "name": "Hot Items", "visible": True, "order": 8},
            {"id": "top_sellers", "name": "Top Sellers", "visible": True, "order": 9},
            {"id": "how_it_works", "name": "How It Works", "visible": True, "order": 10},
            {"id": "trust_features", "name": "Trust Features", "visible": True, "order": 11},
        ]
    },
    "hero_banners": [],  # Will be populated via CRUD
    "updated_at": None,
    "updated_by": None
}

async def get_site_config():
    """Fetch site configuration from database, or return defaults if not set."""
    config = await db.site_config.find_one({"id": "site_config"}, {"_id": 0})
    if not config:
        config = {**DEFAULT_SITE_CONFIG, "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.site_config.insert_one(config)
    return config


@api_router.get("/site-config")
async def get_public_site_config():
    """
    Public endpoint to get site configuration for theming.
    Returns branding, homepage layout, and active banners.
    """
    config = await get_site_config()
    
    # Get active hero banners (simple filter for now)
    active_banners = await db.hero_banners.find(
        {"active": True}, 
        {"_id": 0}
    ).sort("order", 1).to_list(20)
    
    return {
        "branding": config.get("branding", DEFAULT_SITE_CONFIG["branding"]),
        "homepage_layout": config.get("homepage_layout", DEFAULT_SITE_CONFIG["homepage_layout"]),
        "hero_banners": active_banners
    }


@api_router.get("/admin/site-config")
async def get_admin_site_config(current_user: User = Depends(get_current_user)):
    """Get full site configuration (admin only)."""
    if current_user.role != "admin" and not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    config = await get_site_config()
    
    # Get all hero banners
    banners = await db.hero_banners.find({}, {"_id": 0}).sort("order", 1).to_list(100)
    
    return {
        **config,
        "hero_banners": banners
    }


@api_router.put("/admin/site-config/branding")
async def update_site_branding(
    branding_data: Dict,
    current_user: User = Depends(get_current_user)
):
    """Update site branding settings (admin only)."""
    if current_user.role != "admin" and not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get current config
    current_config = await get_site_config()
    old_branding = current_config.get("branding", {}).copy()
    
    # Validate allowed fields
    allowed_fields = ["logo_url", "logo_type", "primary_color", "secondary_color", 
                      "accent_color", "surface_color", "font_family"]
    
    # Validate hex colors
    color_fields = ["primary_color", "secondary_color", "accent_color", "surface_color"]
    for field in color_fields:
        if field in branding_data:
            color = branding_data[field]
            if color and not (color.startswith("#") and len(color) in [4, 7]):
                raise HTTPException(status_code=400, detail=f"Invalid color format for {field}. Use hex format (#RGB or #RRGGBB)")
    
    # Validate font family
    valid_fonts = ["Inter", "Montserrat", "Poppins", "Roboto", "Open Sans", "Lato", "Nunito"]
    if "font_family" in branding_data and branding_data["font_family"] not in valid_fonts:
        raise HTTPException(status_code=400, detail=f"Invalid font. Choose from: {', '.join(valid_fonts)}")
    
    # Build update
    new_branding = {**old_branding}
    for field in allowed_fields:
        if field in branding_data:
            new_branding[field] = branding_data[field]
    
    # Update config
    await db.site_config.update_one(
        {"id": "site_config"},
        {"$set": {
            "branding": new_branding,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": current_user.email
        }},
        upsert=True
    )
    
    # Log the change
    log_entry = {
        "id": str(uuid.uuid4()),
        "action": "BRANDING_UPDATE",
        "admin_id": current_user.id,
        "admin_email": current_user.email,
        "target_type": "site_config",
        "target_id": "branding",
        "details": f"Updated branding: {list(branding_data.keys())}",
        "old_value": old_branding,
        "new_value": new_branding,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.admin_logs.insert_one(log_entry)
    
    logger.info(f"🎨 Site branding updated by {current_user.email}")
    
    return await get_site_config()


@api_router.put("/admin/site-config/homepage-layout")
async def update_homepage_layout(
    layout_data: Dict,
    current_user: User = Depends(get_current_user)
):
    """Update homepage layout settings (admin only)."""
    if current_user.role != "admin" and not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    current_config = await get_site_config()
    old_layout = current_config.get("homepage_layout", {}).copy()
    
    # Validate sections structure
    if "sections" not in layout_data:
        raise HTTPException(status_code=400, detail="sections field is required")
    
    sections = layout_data["sections"]
    if not isinstance(sections, list):
        raise HTTPException(status_code=400, detail="sections must be a list")
    
    # Validate each section
    valid_section_ids = [s["id"] for s in DEFAULT_SITE_CONFIG["homepage_layout"]["sections"]]
    for section in sections:
        if not isinstance(section, dict):
            raise HTTPException(status_code=400, detail="Each section must be an object")
        if "id" not in section or "visible" not in section:
            raise HTTPException(status_code=400, detail="Each section must have 'id' and 'visible' fields")
        if section["id"] not in valid_section_ids:
            raise HTTPException(status_code=400, detail=f"Invalid section id: {section['id']}")
    
    new_layout = {"sections": sections}
    
    # Update config
    await db.site_config.update_one(
        {"id": "site_config"},
        {"$set": {
            "homepage_layout": new_layout,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": current_user.email
        }},
        upsert=True
    )
    
    # Log the change
    log_entry = {
        "id": str(uuid.uuid4()),
        "action": "HOMEPAGE_LAYOUT_UPDATE",
        "admin_id": current_user.id,
        "admin_email": current_user.email,
        "target_type": "site_config",
        "target_id": "homepage_layout",
        "details": "Updated homepage section visibility/order",
        "old_value": old_layout,
        "new_value": new_layout,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.admin_logs.insert_one(log_entry)
    
    logger.info(f"📐 Homepage layout updated by {current_user.email}")
    
    return await get_site_config()


# ==================== HERO BANNER CRUD ====================

@api_router.get("/admin/hero-banners")
async def get_hero_banners(current_user: User = Depends(get_current_user)):
    """Get all hero banners (admin only)."""
    if current_user.role != "admin" and not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    banners = await db.hero_banners.find({}, {"_id": 0}).sort("order", 1).to_list(100)
    return banners


@api_router.post("/admin/hero-banners")
async def create_hero_banner(
    banner_data: Dict,
    current_user: User = Depends(get_current_user)
):
    """Create a new hero banner (admin only)."""
    if current_user.role != "admin" and not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get next order number
    last_banner = await db.hero_banners.find_one(sort=[("order", -1)])
    next_order = (last_banner.get("order", 0) + 1) if last_banner else 0
    
    banner = {
        "id": str(uuid.uuid4()),
        "title": banner_data.get("title", ""),
        "subtitle": banner_data.get("subtitle", ""),
        "image_desktop": banner_data.get("image_desktop"),
        "image_mobile": banner_data.get("image_mobile"),
        "cta_text": banner_data.get("cta_text", "Learn More"),
        "cta_link": banner_data.get("cta_link", "/marketplace"),
        "overlay_opacity": banner_data.get("overlay_opacity", 0.3),
        "text_color": banner_data.get("text_color", "#FFFFFF"),
        "active": banner_data.get("active", True),
        "start_date": banner_data.get("start_date"),
        "end_date": banner_data.get("end_date"),
        "order": next_order,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user.email
    }
    
    await db.hero_banners.insert_one(banner)
    
    # Log
    log_entry = {
        "id": str(uuid.uuid4()),
        "action": "HERO_BANNER_CREATE",
        "admin_id": current_user.id,
        "admin_email": current_user.email,
        "target_type": "hero_banner",
        "target_id": banner["id"],
        "details": f"Created hero banner: {banner['title']}",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.admin_logs.insert_one(log_entry)
    
    logger.info(f"🖼️ Hero banner created by {current_user.email}: {banner['title']}")
    
    # Remove _id before returning
    banner.pop("_id", None)
    return banner


@api_router.put("/admin/hero-banners/{banner_id}")
async def update_hero_banner(
    banner_id: str,
    banner_data: Dict,
    current_user: User = Depends(get_current_user)
):
    """Update a hero banner (admin only)."""
    if current_user.role != "admin" and not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    existing = await db.hero_banners.find_one({"id": banner_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Banner not found")
    
    # Allowed update fields
    allowed_fields = ["title", "subtitle", "image_desktop", "image_mobile", 
                      "cta_text", "cta_link", "overlay_opacity", "text_color",
                      "active", "start_date", "end_date", "order"]
    
    update_data = {k: v for k, v in banner_data.items() if k in allowed_fields}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_data["updated_by"] = current_user.email
    
    await db.hero_banners.update_one({"id": banner_id}, {"$set": update_data})
    
    # Log
    log_entry = {
        "id": str(uuid.uuid4()),
        "action": "HERO_BANNER_UPDATE",
        "admin_id": current_user.id,
        "admin_email": current_user.email,
        "target_type": "hero_banner",
        "target_id": banner_id,
        "details": f"Updated hero banner: {list(update_data.keys())}",
        "old_value": {k: existing.get(k) for k in update_data.keys() if k in existing},
        "new_value": update_data,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.admin_logs.insert_one(log_entry)
    
    updated = await db.hero_banners.find_one({"id": banner_id}, {"_id": 0})
    return updated


@api_router.delete("/admin/hero-banners/{banner_id}")
async def delete_hero_banner(
    banner_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a hero banner (admin only)."""
    if current_user.role != "admin" and not current_user.email.endswith("@admin.bazario.com"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    existing = await db.hero_banners.find_one({"id": banner_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Banner not found")
    
    await db.hero_banners.delete_one({"id": banner_id})
    
    # Log
    log_entry = {
        "id": str(uuid.uuid4()),
        "action": "HERO_BANNER_DELETE",
        "admin_id": current_user.id,
        "admin_email": current_user.email,
        "target_type": "hero_banner",
        "target_id": banner_id,
        "details": f"Deleted hero banner: {existing.get('title')}",
        "deleted_banner": {k: v for k, v in existing.items() if k != "_id"},
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.admin_logs.insert_one(log_entry)
    
    logger.info(f"🗑️ Hero banner deleted by {current_user.email}: {existing.get('title')}")
    
    return {"message": "Banner deleted successfully"}


# Include all API routes - MUST be after all routes are defined
app.include_router(api_router)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

@app.on_event("startup")
async def seed_categories():
    existing_categories = await db.categories.count_documents({})
    if existing_categories == 0:
        categories = [
            {"id": str(uuid.uuid4()), "name_en": "Electronics", "name_fr": "Électronique", "icon": "laptop"},
            {"id": str(uuid.uuid4()), "name_en": "Fashion", "name_fr": "Mode", "icon": "shirt"},
            {"id": str(uuid.uuid4()), "name_en": "Home & Garden", "name_fr": "Maison & Jardin", "icon": "home"},
            {"id": str(uuid.uuid4()), "name_en": "Sports", "name_fr": "Sports", "icon": "dumbbell"},
            {"id": str(uuid.uuid4()), "name_en": "Vehicles", "name_fr": "Véhicules", "icon": "car"},
            {"id": str(uuid.uuid4()), "name_en": "Art & Collectibles", "name_fr": "Art & Objets de collection", "icon": "palette"},
            {"id": str(uuid.uuid4()), "name_en": "Books & Media", "name_fr": "Livres & Médias", "icon": "book"},
            {"id": str(uuid.uuid4()), "name_en": "Toys & Games", "name_fr": "Jouets & Jeux", "icon": "gamepad-2"},
        ]
        await db.categories.insert_many(categories)
        logger.info("Categories seeded successfully")
