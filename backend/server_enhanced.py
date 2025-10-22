from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
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
import os
import logging
import uuid
import asyncio
import aiohttp
import json
import stripe

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
db_name = os.environ['DB_NAME']
jwt_secret = os.environ['JWT_SECRET']
stripe_api_key = os.environ['STRIPE_API_KEY']
google_maps_key = os.environ.get('GOOGLE_MAPS_API_KEY', '')

# Initialize Stripe
stripe.api_key = stripe_api_key

client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# WebSocket Connection Manager for Real-time Features
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.user_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, connection_id: str):
        await websocket.accept()
        if connection_id not in self.active_connections:
            self.active_connections[connection_id] = []
        self.active_connections[connection_id].append(websocket)

    async def connect_user(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.user_connections[user_id] = websocket

    def disconnect(self, websocket: WebSocket, connection_id: str):
        if connection_id in self.active_connections:
            if websocket in self.active_connections[connection_id]:
                self.active_connections[connection_id].remove(websocket)

    def disconnect_user(self, user_id: str):
        if user_id in self.user_connections:
            del self.user_connections[user_id]

    async def broadcast(self, connection_id: str, message: dict):
        if connection_id in self.active_connections:
            for connection in self.active_connections[connection_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass

    async def send_to_user(self, user_id: str, message: dict):
        if user_id in self.user_connections:
            try:
                await self.user_connections[user_id].send_json(message)
            except:
                pass

manager = ConnectionManager()

# ==================== ENHANCED MODELS ====================

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    name: str
    account_type: str
    phone: str
    phone_verified: bool = False
    address: Optional[str] = None
    company_name: Optional[str] = None
    tax_number: Optional[str] = None
    bank_details: Optional[Dict[str, str]] = None
    picture: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    language: str = "en"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    affiliate_code: Optional[str] = None
    referred_by: Optional[str] = None
    seller_rating: float = 0.0
    total_sales: int = 0
    is_top_seller: bool = False
    notification_preferences: Dict[str, bool] = Field(default_factory=lambda: {
        "email_bids": True, "email_messages": True, "email_wins": True,
        "push_bids": True, "push_messages": True, "push_wins": True
    })

class PaymentMethod(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    stripe_payment_method_id: str
    card_brand: str
    last4: str
    exp_month: int
    exp_year: int
    is_verified: bool = False
    is_default: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Message(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    sender_id: str
    receiver_id: str
    content: str
    attachments: List[str] = []
    is_read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Conversation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    participants: List[str]
    listing_id: Optional[str] = None
    last_message: Optional[str] = None
    last_message_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    unread_count: Dict[str, int] = {}

class Report(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    reporter_id: str
    reported_type: str  # 'listing' or 'user'
    reported_id: str
    category: str  # 'fraudulent', 'inappropriate', 'misrepresented', 'spam'
    description: str
    status: str = "pending"  # pending, investigating, resolved, dismissed
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None

class Promotion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    listing_id: str
    seller_id: str
    promotion_type: str  # 'basic', 'power', 'premium'
    price: float
    start_date: datetime
    end_date: datetime
    targeting: Dict[str, Any] = {}
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Notification(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    type: str  # 'bid', 'message', 'win', 'promotion', 'security'
    title: str
    content: str
    link: Optional[str] = None
    is_read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AffiliateEarning(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    affiliate_id: str
    referred_user_id: str
    sale_id: str
    commission_amount: float
    commission_type: str  # 'direct' or 'secondary'
    status: str = "pending"  # pending, paid, cancelled
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    paid_at: Optional[datetime] = None

# ==================== EXISTING MODELS (kept for compatibility) ====================
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
    referred_by: Optional[str] = None

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

class BidCreate(BaseModel):
    listing_id: str
    amount: float

class Bid(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    listing_id: str
    bidder_id: str
    amount: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Category(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name_en: str
    name_fr: str
    icon: str

class SessionCreate(BaseModel):
    session_id: str

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

# ==================== AUTH HELPERS ====================
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, jwt_secret, algorithm="HS256")

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

def generate_affiliate_code() -> str:
    return f"BAZ{uuid.uuid4().hex[:8].upper()}"

# ==================== AUTH ENDPOINTS (Enhanced) ====================
@api_router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pwd = hash_password(user_data.password)
    affiliate_code = generate_affiliate_code()
    
    user = User(
        email=user_data.email, name=user_data.name, account_type=user_data.account_type,
        phone=user_data.phone, address=user_data.address, company_name=user_data.company_name,
        tax_number=user_data.tax_number, bank_details=user_data.bank_details,
        affiliate_code=affiliate_code, referred_by=user_data.referred_by
    )
    
    user_dict = user.model_dump()
    user_dict["password"] = hashed_pwd
    user_dict["created_at"] = user_dict["created_at"].isoformat()
    await db.users.insert_one(user_dict)
    
    # Create affiliate earning if referred
    if user_data.referred_by:
        referrer = await db.users.find_one({"affiliate_code": user_data.referred_by})
        if referrer:
            # Track referral for future commission
            await db.referrals.insert_one({
                "id": str(uuid.uuid4()),
                "affiliate_id": referrer["id"],
                "referred_user_id": user.id,
                "status": "active",
                "created_at": datetime.now(timezone.utc).isoformat()
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
                    account_type="personal", phone="", phone_verified=False,
                    affiliate_code=generate_affiliate_code()
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

# ==================== CONTINUED IN NEXT MESSAGE DUE TO LENGTH ====================
